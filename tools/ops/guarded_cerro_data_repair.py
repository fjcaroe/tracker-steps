"""Run an explicitly scoped, versioned data repair in a fresh copy before Cerro.

The repair module supplies validate_plan(plan) and repair(env, plan). Plans,
backups, logs and certificates remain private. Never changes addon roots.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import importlib
import json
import os
from pathlib import Path
import subprocess

from correct_reception_weights import baseline, digest, query, require


def stable(result):
    return {k:v for k,v in result.items() if k not in ('database','updated_rows','already_applied')}


def main(module_name, ticket):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('rehearse','apply'))
    parser.add_argument('plan', type=Path)
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Root lease and backup privileges required')
    module = importlib.import_module(module_name)
    plan = json.loads(args.plan.read_text())
    module.validate_plan(plan)
    require(plan['ticket'] == ticket, 'Ticket differs')
    config = Path('/etc/odoo18-cerroelplomo.conf')
    stage = args.stage.resolve()
    require(str(stage).startswith(f'/opt/steps-validation/t{ticket}-') and len(stage.parts)==4, 'Private stage required')
    here = Path(__file__).resolve().parent
    identity = {'plan':digest(args.plan), 'tools':{name:digest(here/name) for name in (
        module_name+'.py','guarded_cerro_data_repair.py','correct_reception_weights.py','native_business_profile.py')}}

    def probe(database, label, expected=None):
        code = ('import sys,json\nsys.path.insert(0,'+repr(str(here))+')\nfrom '+module_name+' import repair\n'
                'from guarded_cerro_data_repair import stable\nresult=repair(env,'+repr(plan)+')\n')
        if expected is not None:
            code += 'assert stable(result)=='+repr(stable(expected))+', "Result differs from certified copy"\n'
        code += 'env.cr.commit()\nprint("GUARDED_REPAIR_OK "+json.dumps(result))\n'
        process = subprocess.run(['sudo','-u','cerro_odoo18','/usr/bin/python3.10','/opt/odoo18/odoo-bin',
            'shell','-c',str(config),'-d',database,'--db-filter=^'+database+'$','--no-http',
            '--workers=0','--max-cron-threads=0','--log-level=critical'],input=code,text=True,capture_output=True)
        (stage/(label+'.log')).write_text(process.stdout+process.stderr)
        lines = [line.split('GUARDED_REPAIR_OK ',1)[1] for line in process.stdout.splitlines() if line.startswith('GUARDED_REPAIR_OK ')]
        require(process.returncode==0 and len(lines)==1, 'Probe failed; inspect private '+label+'.log')
        return json.loads(lines[0])

    def backup(path):
        with path.open('xb') as stream:
            os.fchmod(stream.fileno(),0o600)
            subprocess.run(['sudo','-u','postgres','pg_dump','-Fc',plan['database']],stdout=stream,check=True)
        with path.open('rb') as stream:
            subprocess.run(['sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments',
                            '--file=/dev/null'],stdin=stream,check=True)

    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX | fcntl.LOCK_NB)
        for entry in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                argv=entry.read_bytes().decode(errors='replace').split('\0')
            except OSError:
                continue
            if any(Path(arg).name=='odoo-bin' for arg in argv):
                require(not any(arg in ('-u','-i','--update','--init') or arg.startswith(('--update=','--init=')) for arg in argv), 'Concurrent upgrade')
        current = baseline(config)
        if args.mode == 'rehearse':
            stage.mkdir(mode=0o700,exist_ok=False)
            clone=f'MANAGEMENT_QA_CERRO_t{ticket}_'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            require(not query('postgres',"SELECT 1 FROM pg_database WHERE datname='"+clone+"'"), 'Fresh copy required')
            backup(stage/'source.dump')
            subprocess.run(['sudo','-u','postgres','createdb','-O','cerro_odoo18',clone],check=True)
            query(clone,'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
            with (stage/'source.dump').open('rb') as stream:
                subprocess.run(['sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments',
                                '--role','cerro_odoo18','-d',clone],stdin=stream,check=True)
            query(clone,'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
            tested=probe(clone,'clone')
            repeated=probe(clone,'clone-idempotent',tested)
            require(tested['updated_rows']>0 and not repeated['updated_rows'] and repeated['already_applied'], 'Idempotency failed')
            require(current==baseline(config), 'Runtime changed during rehearsal')
            proof={'identity':identity,'baseline':current,'clone':clone,'tested':tested,'idempotent':repeated}
            (stage/'certificate.json').write_text(json.dumps(proof,indent=2))
            print('GUARDED_REPAIR_CERTIFIED '+json.dumps({'ticket':ticket,'clone':clone,'idempotent':True}))
        else:
            proof=json.loads((stage/'certificate.json').read_text())
            require(identity==proof['identity'] and current==proof['baseline'], 'Plan/tools/runtime differ from certified copy')
            require(not (stage/'live.json').exists(), 'Delivery already recorded')
            backup(stage/'before-live.dump')
            (stage/'odoo.conf').write_bytes(config.read_bytes());(stage/'odoo.conf').chmod(0o600)
            live=probe(plan['database'],'live',proof['tested'])
            (stage/'live.json').write_text(json.dumps({'result':live,'identity':identity,
                'backup_sha256':digest(stage/'before-live.dump')},indent=2))
            print('GUARDED_REPAIR_APPLIED '+json.dumps({'ticket':ticket,'receipts':len(live['receipts']),
                  'tags':len(live['tags']),'updated_rows':live['updated_rows'],'missing':live['missing_receipts']}))
