"""Print existing commercial documents read-only on a registry-selected target."""
import argparse
import configparser
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import re
import subprocess

here = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('environment', choices=('development', 'cerro'))
p.add_argument('--qa-run-id')
p.add_argument('--company-name', help='Exact, unambiguous company for read-only examples')
a = p.parse_args()
target = json.loads((here/'environments.json').read_text())['environments'][a.environment]
cfg = configparser.ConfigParser(interpolation=None); cfg.read(target['config']); opts = cfg['options']
assert opts['db_name'] == target['database'] and int(opts['http_port']) == target['port']
user = subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
database = target['database']; extra = []
if a.qa_run_id:
    assert re.fullmatch('[a-z0-9_]{1,24}', a.qa_run_id)
    stage = Path('/opt/steps-validation')/('management_'+a.environment+'_'+a.qa_run_id)
    database = json.loads((stage/'qa_passed.json').read_text())['database']
    extra = ['--addons-path='+str(stage/'addons')+','+opts['addons_path'], '--data-dir='+str(stage/'data')]
    output = stage/'actual-preview'
else:
    output = Path('/opt/steps-validation')/('documents_actual_'+a.environment+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
output.mkdir(mode=0o750,exist_ok=True)
identity = pwd.getpwnam(user); os.chown(output,identity.pw_uid,identity.pw_gid)
script = '''
from pathlib import Path
import json
try:
    company = env['res.company'].search([('name','=',COMPANY_NAME)],limit=2) if COMPANY_NAME else env.company
    assert len(company) == 1, 'Select one company explicitly'
    env = env(context=dict(env.context,allowed_company_ids=company.ids))
    reports = env['ir.actions.report']
    order = env['sale.order'].search(['|','|',('step_export_sale','=',True),('step_export_shipment_id','!=',False),('step_export_sales_program_id','!=',False),('company_id','=',company.id)],order='id desc',limit=1)
    packing = env['step.export.packing.list'].search([('company_id','=',company.id)],order='id desc',limit=1)
    for record, report, filename in [(order,'step_sale_export_report.proforma','customer-proforma'),
        (order,'step_export_document_revision.commercial_invoice','customer-invoice'),
        (packing,'step_export.action_report_export_packing_list','customer-packing')]:
        if not record:
            continue
        record = record.with_company(record.company_id)
        pdf,_ = reports._render_qweb_pdf(report, record.ids)
        assert pdf.startswith(b'%PDF')
        Path(OUTPUT,filename+'.pdf').write_bytes(pdf)
    if packing:
        Path(OUTPUT,'customer-packing.xlsx').write_bytes(packing._document_xlsx())
    print('CURRENT_DOCUMENTS_OK '+json.dumps({'order':order.id or None,'packing':packing.id or None,'output':OUTPUT}))
finally:
    env.cr.rollback()
'''
result = subprocess.run(['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',target['config'],
    '-d',database,'--db-filter=^'+database+'$','--no-http','--workers=0','--max-cron-threads=0','--log-level=error']+extra,
    input='OUTPUT='+repr(str(output))+'\nCOMPANY_NAME='+repr(a.company_name)+'\n'+script,text=True,capture_output=True)
(output/'render.log').write_text(result.stdout+result.stderr)
assert result.returncode == 0 and 'CURRENT_DOCUMENTS_OK' in result.stdout, 'Inspect '+str(output/'render.log')
print('\n'.join(line for line in result.stdout.splitlines() if line.startswith('CURRENT_DOCUMENTS_OK')))
