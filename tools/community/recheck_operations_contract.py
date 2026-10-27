"""Finish contracts after successful full tests, without changing tested addons.

Restores the original dump to a NEW private SQL-only baseline. Its unfiltered
history must exactly match the recorded pre-upgrade history before applying
the narrowly tested compiled-cache exception. Never upgrades or deploys Odoo.
"""
import argparse
import configparser
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import validate_agriculture_core as v


def file_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--baseline-database', required=True)
    args = parser.parse_args()
    for database in (args.database, args.baseline_database):
        assert re.fullmatch(r'MANAGEMENT_QA_CERRO_AGRICULTURE_OPERATIONS_[A-Za-z0-9_]+', database)
    assert args.database != args.baseline_database
    root = args.root.resolve(); stage = root / 'cerro-copy'; addons = root / 'addons'
    v.MODULES = v.BASE_MODULES + v.PRODUCER_MODULES + v.OPERATIONS_MODULES
    recorded = json.loads((stage / 'source-files.json').read_text())
    actual = {str(p.relative_to(addons)): hashlib.sha256(p.read_bytes()).hexdigest()
              for module in v.MODULES for p in sorted((addons / module).rglob('*'))
              if p.is_file() and '__pycache__' not in p.parts}
    assert recorded == actual, 'Tested addon package changed'
    assert recorded == json.loads((root / 'community/source-files.json').read_text())
    pure = json.loads((root / 'community/passed.json').read_text())
    assert pure['mode'] == 'community' and pure['profile'] == 'operations'
    assert pure['database'].startswith('COMMUNITY_AGRICULTURE_OPERATIONS_')
    # Exactly the entire operations profile, never a focused diagnostic run.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ops'))
    from manage_management import errors
    for mode in ('community', 'cerro-copy'):
        log = (root / mode / 'tests.log').read_text()
        assert not errors(log, ('steps_api',) if mode == 'cerro-copy' else ())
        assert re.search(r'0 failed, 0 error\(s\) of 408 tests', log), mode
        assert 'OPERATIONS_NATIVE_OK' in (root / mode / 'verify.log').read_text(), mode
    conf = Path('/etc/odoo18-cerroelplomo.conf')
    config = configparser.ConfigParser(interpolation=None); assert config.read(conf)
    options = config['options']; assert options['db_name'] == 'CERRO_EL_PLOMO'
    source = json.loads((stage / 'source-contract.json').read_text())
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert v.source_contract(conf, addons) == source
        assert not v.sql('postgres', "SELECT 1 FROM pg_database WHERE datname='" + args.baseline_database + "'")
        v.run('sudo', '-u', 'postgres', 'createdb', args.baseline_database)
        with (stage / 'source.dump').open('rb') as stream:
            v.run('sudo', '-u', 'postgres', 'pg_restore', '--no-owner', '--no-acl', '--no-comments',
                  '-d', args.baseline_database, stdin=stream)
        # No Odoo runtime ever connects to this baseline. Disable schedulers
        # and delivery defensively even though only read-only SQL follows.
        v.sql(args.baseline_database, 'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        v.MODULES = v.BASE_MODULES
        raw_history = v.history_contract(args.baseline_database)
        assert raw_history == json.loads((stage / 'history-before.json').read_text()), 'Dump baseline history differs'
        v.MODULES = v.BASE_MODULES + v.PRODUCER_MODULES + v.OPERATIONS_MODULES
        history = v.history_contract(args.baseline_database)
        before = json.loads((stage / 'business-before.json').read_text())
        assert v.same_values(before, v.snapshot(args.baseline_database)), 'Dump baseline business differs'
        original = json.loads((stage / 'identity-before.json').read_text())
        assert original == v.identity_contract(args.baseline_database), 'Dump baseline identities differ'
        base = ['sudo', '-u', 'cerro_odoo18', '/usr/bin/python3.10', '/opt/odoo18/odoo-bin']
        opts = ['-c', str(conf), '-d', args.database, '--db-filter=^' + args.database + '$',
                '--addons-path=' + str(addons) + ',' + options['addons_path'],
                '--data-dir=' + str(stage / 'data'), '--load=base,web', '--workers=0', '--max-cron-threads=0']
        v.verify_native(base, opts, addons, stage, 'cerro-copy')
        after = v.snapshot(args.database)
        current = v.identity_contract(args.database)
        final_history = v.history_contract(args.database)
        assert v.same_values(before, after), 'Business values changed'
        bindings = json.loads((stage / 'calendar-bindings-before.json').read_text())
        assert len(bindings) == 2
        for table, rows in original.items():
            if table in ('ir_model', 'ir_model_fields'):
                now = {r['id']: r for r in current[table]}
                for row in rows:
                    got = now.get(row['id'])
                    assert got and all(got[k] == val for k, val in row.items() if k != 'modules'), (table,row['id'])
            else:
                expected = [dict(row,view_mode='calendar') if table == 'ir_act_window_view' and
                            row['id'] in bindings and row['view_mode'] in ('gantt','calendar') else row for row in rows]
                assert all(row in current[table] for row in expected), table
        assert final_history == history, 'Business attachments, history or expiration changed'
        assert v.source_contract(conf, addons) == source, 'Source runtime changed'
        for name, value in [('business-after',after),('identity-after',current),
                            ('history-before-business',history),('history-after-business',final_history)]:
            (stage / (name + '.json')).write_text(json.dumps(value,indent=2))
        proof = {'mode':'cerro-copy','database':args.database,'profile':'operations','environment':'cerro',
                 'business_preserved':True,'writes_to_source':False,'files':len(recorded),
                 'baseline_database':args.baseline_database,'modules':v.MODULES,
                 'method':'Full 408 tests in each runtime, exact addons, dump-backed cache contract recheck',
                 'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 'validator_sha256':hashlib.sha256(Path(v.__file__).read_bytes()).hexdigest(),
                 'test_log_sha256':hashlib.sha256((stage/'tests.log').read_bytes()).hexdigest(),
                 'dump_sha256':file_digest(stage/'source.dump')}
        (stage/'passed.json').write_text(json.dumps(proof,indent=2))
        print('OPERATIONS_CONTRACT_OK',len(before),'business tables/projections')


if __name__ == '__main__':
    main()
