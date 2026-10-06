"""Rehearse, then atomically add synthetic Productores records in Desarrollo.

No addon upgrade or service restart. Rehearsal rolls back on a passed private
clone. Apply requires the same script and runtime, a backup and the shared lock.
"""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
MODULES = ('step_producers', 'step_producer_fruit_flow', 'step_producers_integrations',
           'step_export', 'step_packing_operations', 'step_inventory_packing', 'step_dispatch_guide')


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def sql(database, statement):
    return subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1',
                                    '-d', database, '-Atc', statement], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('rehearse', 'apply', 'verify'))
    parser.add_argument('--clone-stage', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    registry = json.loads((HERE / 'environments.json').read_text())
    target = registry['environments']['development']
    assert registry['policy']['qa'] == 'development' and target['database'] == 'LAB_TAREAS'
    conf = Path(target['config'])
    cfg = configparser.ConfigParser(interpolation=None); cfg.read(conf)
    opts = cfg['options']; assert opts['db_name'] == target['database']
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
    identity = pwd.getpwnam(user)
    args.stage.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(args.stage, identity.pw_uid, identity.pw_gid)
    passed = json.loads((args.clone_stage / 'qa_passed.json').read_text())
    clone = passed['database']; assert clone.startswith('MANAGEMENT_QA_DEVELOPMENT_')
    assert json.loads((args.clone_stage / 'addons/release.json').read_text())['commit'] == passed['commit']
    addon_paths = ([str(args.clone_stage / 'addons')] if args.mode == 'rehearse' else []) + opts['addons_path'].split(',')
    sources = {}
    for name in MODULES:
        source = next(Path(root.strip()) / name for root in addon_paths
                      if (Path(root.strip()) / name / '__manifest__.py').exists())
        sources[name] = {str(file.relative_to(source)): digest(file) for file in sorted(source.rglob('*'))
                         if file.is_file() and file.suffix in ('.py', '.xml', '.csv') and '__pycache__' not in file.parts}
    baseline = {'config_sha256': digest(conf), 'seed_sha256': digest(HERE / 'seed_producer_sample.py'), 'sources': sources}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    log = args.stage / (args.mode + '-' + stamp + '.log')
    certificate = args.stage / 'rehearsal.json'
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not sql(target['database'], "SELECT name FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove')"), 'Concurrent pending upgrade'
        for cmdline in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                argv = cmdline.read_bytes().decode(errors='replace').split('\x00')
            except OSError:
                continue
            if any(Path(arg).name == 'odoo-bin' for arg in argv):
                assert not any(arg in ('-u', '-i', '--update', '--init') or arg.startswith(('--update=', '--init=')) for arg in argv), 'Concurrent Odoo upgrade'
        database = clone if args.mode == 'rehearse' else target['database']
        versions = json.loads(sql(database, "SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed' AND name IN (%s)" % ','.join("'%s'" % name for name in MODULES)))
        assert set(versions) == set(MODULES)
        baseline['versions'] = versions
        if args.mode == 'apply':
            assert json.loads(certificate.read_text())['baseline'] == baseline, 'Repeat rehearsal after runtime/source changes'
            backup = Path('/opt/steps_backups') / ('producers_sample_development_' + stamp)
            backup.mkdir(mode=0o700)
            with (backup / 'database.dump').open('wb') as stream:
                subprocess.run(['sudo', '-u', 'postgres', 'pg_dump', '-Fc', target['database']], stdout=stream, check=True)
            (backup / 'script_sha256.txt').write_text(baseline['seed_sha256'])
            print('SAMPLE_BACKUP_OK ' + str(backup), flush=True)
        seed_source = (HERE / 'seed_producer_sample.py').read_text()
        header = 'MODE=' + repr(args.mode) + '\nEXPECTED_DB=' + repr(database) + '\n'
        tail = """
assert env.cr.dbname == EXPECTED_DB
env.cr.rollback()
env.cr.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
before = business_fingerprints(env)
try:
    if MODE == 'verify':
        manifest = verify_manifest(env, json.loads(env['ir.config_parameter'].sudo().get_param(MARKER)))
    else:
        manifest = seed(env)
        assert_preserved(before, business_fingerprints(env))
        # An unchanged rerun must preserve every row, including the test data.
        after = business_fingerprints(env)
        assert seed(env) == manifest
        assert business_fingerprints(env) == after
    print('PRODUCER_SAMPLE_OK ' + json.dumps(manifest))
    if MODE == 'apply':
        env.cr.commit()
    else:
        env.cr.rollback()
except BaseException:
    env.cr.rollback()
    raise
"""
        command = ['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', 'shell',
                   '-c', str(conf), '-d', database, '--db-filter=^' + database + '$',
                   '--no-http', '--workers=0', '--max-cron-threads=0', '--logfile=' + str(log)]
        if args.mode == 'rehearse':
            command.append('--data-dir=' + str(args.clone_stage / 'data'))
            command.append('--addons-path=' + ','.join(addon_paths))
        result = subprocess.run(command, input=header + seed_source + tail, text=True, capture_output=True)
        output = args.stage / (args.mode + '-' + stamp + '-result.log')
        output.write_text(result.stdout + result.stderr)
        line = next((line for line in result.stdout.splitlines() if line.startswith('PRODUCER_SAMPLE_OK ')), '')
        if result.returncode or not line:
            print(result.stderr[-4000:], flush=True)
            raise AssertionError('Sample did not complete: ' + str(output))
        manifest = json.loads(line.removeprefix('PRODUCER_SAMPLE_OK '))
        if args.mode == 'rehearse':
            assert not sql(clone, "SELECT value FROM ir_config_parameter WHERE key='steps.qa.productores.walkthrough.v1'"), 'Rehearsal must roll back'
            certificate.write_text(json.dumps({'baseline': baseline, 'log': str(log), 'summary': manifest['summary']}, indent=2))
        else:
            (args.stage / 'live_manifest.json').write_text(json.dumps(manifest, indent=2))
        print('PRODUCER_SAMPLE_' + args.mode.upper() + '_OK ' + json.dumps(manifest['summary']), flush=True)


if __name__ == '__main__':
    main()
