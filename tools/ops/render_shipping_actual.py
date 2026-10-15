"""Render an existing instruction read-only, in its target or an approved private copy."""
import argparse
import configparser
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import re
import subprocess

here=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro'))
p.add_argument('--qa-run-id')
a=p.parse_args()
target=json.loads((here/'environments.json').read_text())['environments'][a.environment]
cfg=configparser.ConfigParser(interpolation=None);cfg.read(target['config']);opts=cfg['options']
assert opts['db_name']==target['database'] and int(opts['http_port'])==target['port']
user=subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
database=target['database'];extra=[]
if a.qa_run_id:
    assert re.fullmatch('[a-z0-9_]{1,24}',a.qa_run_id)
    stage=Path('/opt/steps-validation')/('management_'+a.environment+'_'+a.qa_run_id)
    database=json.loads((stage/'qa_passed.json').read_text())['database']
    extra=['--addons-path='+str(stage/'addons')+','+opts['addons_path'], '--data-dir='+str(stage/'data')]
    output=stage/'actual-preview'
else:
    output=Path('/opt/steps-validation')/('shipping_actual_'+a.environment+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
output.mkdir(mode=0o750,exist_ok=True)
identity=pwd.getpwnam(user);os.chown(output,identity.pw_uid,identity.pw_gid)
script="""
import json
from pathlib import Path
try:
    module=env['ir.module.module'].search([('name','=','step_export_shipping_design')])
    assert module.latest_version=='18.0.1.0.1' and module.state=='installed'
    record=env['step.export.export'].search([],order='id desc',limit=1)
    assert record
    record=record.with_company(record.company_id)
    reports=record.env['ir.actions.report']
    action=record.env.ref('step_export_shipping_design.instruction_report')
    assert not action.attachment_use and not action.attachment
    html,_=reports._render_qweb_html('step_export_shipping_design.instruction',record.ids)
    pdf,_=reports._render_qweb_pdf('step_export_shipping_design.instruction',record.ids)
    assert pdf.startswith(b'%PDF')
    Path(OUTPUT,'customer-instruction.pdf').write_bytes(pdf)
    Path(OUTPUT,'customer-instruction.html').write_bytes(html)
    print('CURRENT_SHIPPING_PDF '+json.dumps({'version':module.latest_version,'record':record.id,'state':record.state,'bytes':len(pdf),'output':OUTPUT}))
finally:
    env.cr.rollback()
"""
result=subprocess.run(['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',target['config'],
    '-d',database,'--db-filter=^'+database+'$','--no-http','--workers=0','--max-cron-threads=0','--log-level=error']+extra,
    input='OUTPUT='+repr(str(output))+'\n'+script,text=True,capture_output=True)
(output/'render.log').write_text(result.stdout+result.stderr)
assert result.returncode==0 and 'CURRENT_SHIPPING_PDF' in result.stdout, 'Inspect '+str(output/'render.log')
print('\n'.join(line for line in result.stdout.splitlines() if line.startswith('CURRENT_SHIPPING_PDF')))
