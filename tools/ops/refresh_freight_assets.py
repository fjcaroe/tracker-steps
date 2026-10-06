"""Regenerate only Odoo's compiled asset cache for the verified freight release."""
import argparse
import configparser
import fcntl
import json
import os
from pathlib import Path
import subprocess

from manage_management import digest, query


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release', type=Path)
    parser.add_argument('run_id')
    parser.add_argument('--clone', action='store_true')
    args = parser.parse_args()
    registry = json.loads((Path(__file__).parent / 'environments.json').read_text())
    target = registry['environments']['development']
    stage = Path('/opt/steps-validation') / ('freight_development_' + args.run_id)
    passed = json.loads((stage / 'qa_passed.json').read_text())
    assert passed['sha256'] == digest(args.release)
    proof = json.loads((stage / 'addons/release.json').read_text())
    assert proof['commit'] == passed['commit']
    assert proof['versions']['step_operations_ui'] == '18.0.2.6.0'
    database = passed['database'] if args.clone else target['database']
    source = stage / 'addons' if args.clone else Path('/opt/steps-managed/freight/development') / passed['commit']
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(target['config'])
    options = cfg['options']
    data = stage / 'data' if args.clone else Path(options['data_dir'])
    user = subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
    script = 'ROOT=' + repr(str(source)) + '\nVERSIONS=' + repr(proof['versions']) + '\n'
    script += """
import importlib,json
for name,version in VERSIONS.items():
    module=env['ir.module.module'].search([('name','=',name)])
    assert module.latest_version==version and module.state=='installed'
    assert importlib.import_module('odoo.addons.'+name).__file__.startswith(ROOT+'/')
cache_domain=[('public','=',True),('url','=like','/web/assets/%'),('res_model','=','ir.ui.view'),('res_id','=',0),('create_uid','=',1)]
count=env['ir.attachment'].search_count(cache_domain)
env['ir.attachment'].regenerate_assets_bundles()
assert not env['ir.attachment'].search_count(cache_domain)
env.registry.signal_changes()
env.cr.commit()
print('FREIGHT_ASSETS_REFRESHED '+json.dumps({'database':env.cr.dbname,'generated_bundles':count}))
"""
    with open('/run/lock/steps-environments.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Git-built archives use epoch timestamps. Odoo includes max file
        # mtime in the browser asset URL; make the URL change as well as bytes.
        # Only metadata of private, already verified static files is changed.
        for addon in proof['versions']:
            for file in (source / addon / 'static').rglob('*'):
                if file.is_file():
                    os.utime(file, None)
        before = query(database, "SELECT count(*)::text||':'||COALESCE(sum(amount_total),0)::text FROM account_move")
        result = subprocess.run(['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell',
            '-c',target['config'],'-d',database,'--db-filter=^'+database+'$','--no-http','--workers=0',
            '--max-cron-threads=0','--data-dir='+str(data),'--addons-path='+str(source)+','+options['addons_path'],
            '--log-level=error'],input=script,text=True,capture_output=True)
        (stage / ('assets-' + database + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode==0 and 'FREIGHT_ASSETS_REFRESHED' in result.stdout, result.stderr[-1500:]
        assert query(database, "SELECT count(*)::text||':'||COALESCE(sum(amount_total),0)::text FROM account_move") == before
        print('\n'.join(line for line in result.stdout.splitlines() if line.startswith('FREIGHT_ASSETS_REFRESHED')))


if __name__ == '__main__':
    main()
