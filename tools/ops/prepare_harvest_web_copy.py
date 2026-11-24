"""Certify an unchanged Harvest backend in a fresh copy for a static-only update.

No addons are updated and no source service, credentials or business records change.
The exact frontend manifest is bound to the copy; browser review is still required.
"""
import argparse
import configparser
from contextlib import nullcontext
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess

import manage_management as management
from customer_qa_clone_access import clone_database_access
from provision_cerro_qa import business_snapshot
from publish_harvest_web import validate


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=('development', 'cerro', 'qa-cerro'))
    parser.add_argument('--web', required=True, type=Path)
    parser.add_argument('--backend', required=True, type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0
    web = args.web
    assert web.resolve() == web and web.is_relative_to('/opt/steps-validation')
    frontend = validate(web)
    assert frontend['version'] == '0.0.4'
    run_id = 'harvestcompany_'+frontend['commit'][:8]
    stage = Path('/opt/steps-validation')/('management_'+args.environment+'_'+run_id)
    database = 'MANAGEMENT_QA_'+args.environment.upper()+'_'+run_id
    tools = Path(__file__).resolve().parent
    target = json.loads((tools/'environments.json').read_text())['environments'][args.environment]
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(target['config'])
    options = cfg['options']
    assert options['db_name'] == target['database']
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
    identity = pwd.getpwnam(user)
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        print('HARVEST_WEB_COPY_WAITING_FOR_LEASE', flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        assert not stage.exists(), 'Fresh copy required; preserve previous evidence'
        assert not management.query('postgres', "SELECT 1 FROM pg_database WHERE datname='%s'" % database)
        assert management.query(target['database'], "SELECT count(*) FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove')") == '0'
        for command in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                argv = command.read_bytes().decode(errors='replace').split('\x00')
            except OSError:
                continue
            for index, value in enumerate(argv):
                if Path(value).name == 'odoo-bin':
                    assert not any(option in ('-u', '-i', '--update', '--init') or option.startswith(('--update=', '--init=')) for option in argv[index+1:]), 'Concurrent addon update'
        management.MODULES = ('step_cosecha_operations', 'step_harvest_launcher')
        source_bytes = int(management.query(target['database'], 'SELECT pg_database_size(current_database())'))
        stat = os.statvfs(Path(management.query('postgres', 'SHOW data_directory')))
        assert stat.f_bavail * stat.f_frsize >= max(1024**3, 2 * source_bytes + 512 * 1024**2)
        stage.mkdir(mode=0o755)
        addons = stage/'addons'
        addons.mkdir()
        backend = management.extract(args.backend, addons)
        roots = [Path(path.strip()) for path in options['addons_path'].split(',')]
        baseline = {'config_sha256': management.digest(Path(target['config'])), 'modules': {}}
        for module, expected_version in backend['versions'].items():
            version = management.query(target['database'], "SELECT latest_version FROM ir_module_module WHERE name='%s' AND state='installed'" % module)
            assert version == expected_version
            effective = next(root/module for root in roots if (root/module/'__manifest__.py').is_file())
            assert management.tree_hash(effective) == management.tree_hash(addons/module), 'Read-only review cannot change backend code'
            baseline['modules'][module] = {'version': version, 'sha256': management.tree_hash(effective)}
        (stage/'baseline.json').write_text(json.dumps(baseline, indent=2))
        access = clone_database_access(management.query, database, stage) if args.environment == 'qa-cerro' else nullcontext()
        with access:
            print('HARVEST_WEB_COPY_BEGIN '+database, flush=True)
            with (stage/'source.dump').open('wb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', target['database'], stdout=stream)
            run('sudo', '-u', 'postgres', 'createdb', '-O', options['db_user'], database)
            with (stage/'source.dump').open('rb') as stream:
                run('sudo', '-u', 'postgres', 'pg_restore', '--no-owner', '--no-acl', '--no-comments', '--role', options['db_user'], '-d', database, stdin=stream)
            before = business_snapshot(database)
            (stage/'business_before.json').write_text(json.dumps(before, indent=2))
            management.query(database, "UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false; UPDATE fetchmail_server SET active=false; INSERT INTO ir_config_parameter(key,value) VALUES ('database.is_neutralized','true') ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value")
            data = stage/'data'
            data.mkdir(mode=0o700)
            source_store = Path(options['data_dir'])/'filestore'/target['database']
            destination = data/'filestore'/database
            destination.mkdir(parents=True)
            if source_store.exists():
                run('rsync', '-a', str(source_store)+'/', str(destination)+'/')
            for path in [data, *data.rglob('*')]:
                os.chown(path, identity.pw_uid, identity.pw_gid)
            native = ['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', 'shell',
                '-c', target['config'], '-d', database, '--db-filter=^'+database+'$', '--no-http',
                '--workers=0', '--max-cron-threads=0', '--addons-path='+str(addons)+','+options['addons_path'],
                '--data-dir='+str(data), '--log-level=error']
            probe = 'EXPECTED='+repr(backend['versions'])+'\nROOT='+repr(str(addons))+'\n'+(tools/'verify_harvest_operations.py').read_text()
            result = subprocess.run(native, input=probe, text=True, capture_output=True)
            log = stage/('verify-'+database+'.log')
            log.write_text(result.stdout+result.stderr)
            assert result.returncode == 0 and 'MANAGEMENT_REGISTRY_OK' in result.stdout, str(log)
            assert business_snapshot(database) == before, 'Native review must preserve all original business records'
            assert baseline['config_sha256'] == management.digest(Path(target['config']))
            proof = {'feature': 'harvest-company-selector', 'readonly_copy': True,
                'commit': backend['commit'], 'release_sha256': management.digest(args.backend),
                'database': database, 'log': str(log), 'harvest_web': frontend,
                'business_preserved': True, 'created_at': datetime.now(timezone.utc).isoformat()}
            (stage/'qa_passed.json').write_text(json.dumps(proof, indent=2))
        print('HARVEST_WEB_COPY_OK '+json.dumps({'stage': str(stage), 'database': database,
            'web_commit': frontend['commit'], 'backend_commit': backend['commit'], 'business_preserved': True}), flush=True)


if __name__ == '__main__':
    main()
