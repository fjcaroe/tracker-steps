"""Configure a missing native interplant type in customer QA after a rolled-back copy test."""
import argparse
import configparser
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import subprocess
from customer_qa_clone_access import clone_database_access
from manage_management import query

SCRIPT = '''
import json
from odoo import Command
from native_business_profile import scoped_business_environment
assert env.cr.dbname == EXPECTED_DB
source=env['res.company'].browse(SOURCE)
destination=env['res.company'].browse(DESTINATION)
assert source.exists() and destination.exists() and source != destination and source.root_id == destination.root_id
business=scoped_business_environment(env,company=source)
assert destination in business.user.company_ids
kinds=business['step.freight.dispatch.type']
previous=kinds.search([]).read(['name','step_recipient_kind','company_ids'])
kind=kinds.search([('name','=','Traslado Interplanta')])
if kind:
    assert len(kind)==1 and kind.step_recipient_kind=='interplant'
    assert set(kind.company_ids.ids)=={SOURCE,DESTINATION}
else:
    assert not kinds.sudo().search_count([('name','=','Traslado Interplanta')])
    kind=kinds.create({'name':'Traslado Interplanta','step_recipient_kind':'interplant',
                      'company_ids':[Command.set([SOURCE,DESTINATION])]})
assert kinds.browse([r['id'] for r in previous]).read(['name','step_recipient_kind','company_ids'])==previous
for origin,target in ((source,destination),(destination,source)):
    scoped=business['step.dispatch.guide'].with_company(origin)
    guide=scoped.new({'company_id':origin.id,'partner_id':target.partner_id.id,'dispatch_type_id':kind.id})
    guide._onchange_interplant_destination()
    assert guide.step_destination_company_id==target and guide.step_destination_warehouse_id.with_company(target).company_id==target
    guide._check_recipient()
    guide._check_dispatch_type_company()
print('NATIVE_QA_TYPE_CHECK_OK '+json.dumps({'type':kind.id,'companies':kind.company_ids.ids,'both_directions':True,'apply':APPLY}))
if APPLY: env.cr.commit()
else: env.cr.rollback()
'''
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('run_id');parser.add_argument('source',type=int);parser.add_argument('destination',type=int)
parser.add_argument('--apply',action='store_true');args=parser.parse_args()
assert re.fullmatch(r't209[a-z]+',args.run_id)
root=Path(__file__).resolve().parent
entry=json.loads((root/'environments.json').read_text())['environments']['qa-cerro']
assert entry['database']=='QA-CERROELPLOMO'
stage=Path('/opt/steps-validation')/('management_qa-cerro_'+args.run_id)
qa=json.loads((stage/'qa_passed.json').read_text())
config=configparser.ConfigParser(interpolation=None);config.read(entry['config'])
assert config['options']['addons_path'].split(',')[0].endswith(qa['commit'])
user=subprocess.check_output(['systemctl','show','--value','--property=User',entry['service']],text=True).strip()
def execute(database,apply):
    header='import sys\nsys.path.insert(0,'+repr(str(root))+')\n'
    for key,value in {'EXPECTED_DB':database,'SOURCE':args.source,'DESTINATION':args.destination,'APPLY':apply}.items():header+=key+'='+repr(value)+'\n'
    command=['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',entry['config'],'-d',database,'--no-http','--workers=0','--max-cron-threads=0','--log-level=error']
    if not apply: command+=['--data-dir='+str(stage/'data')]
    result=subprocess.run(command,input=header+SCRIPT,text=True,capture_output=True)
    (stage/('native-type-live.log' if apply else 'native-type-copy.log')).write_text(result.stdout+result.stderr)
    assert result.returncode==0 and 'NATIVE_QA_TYPE_CHECK_OK' in result.stdout,result.stderr[-2500:]
    print(result.stdout.strip())
with open('/run/lock/steps-environments.lock','a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
    with clone_database_access(query,qa['database'],stage,existing=True):execute(qa['database'],False)
    if args.apply:
        backup=Path('/opt/steps_backups')/('qa_interplant_type_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(mode=0o700)
        with (backup/'database.dump').open('wb') as out:
            subprocess.run(['sudo','-u','postgres','pg_dump','-Fc',entry['database']],stdout=out,check=True)
        tables=('step_dispatch_guide','stock_picking','stock_move','stock_move_line','stock_quant','stock_quant_package','account_move','account_move_line')
        def preservation():
            return {table:query(entry['database'],"SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'|' ORDER BY to_jsonb(t)::text),'')) FROM "+table+' t') for table in tables}
        before=preservation();execute(entry['database'],True);assert preservation()==before
        (backup/'configuration.json').write_text(json.dumps({'source':args.source,'destination':args.destination,'copy':qa['database'],'business_preserved':True}))
        print('NATIVE_QA_TYPE_CONFIGURED backup='+str(backup))
