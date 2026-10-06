"""Restore the native report overwritten by the retired payroll engine."""
from odoo import tools

assert env.cr.dbname == EXPECTED_DATABASE
view=env.ref('hr_payroll.report_payslip')
if "worked_days_table" not in view.arch_db:
    assert 'o.contract_id.afp_id' in view.arch_db, 'Unknown custom payslip template; do not overwrite'
    archive=env['step.payroll.legacy.snapshot'].sudo()
    if not archive.search_count([('source_model','=','ir.ui.view'),('source_id','=',view.id)]):
        archive.create({'source_model':'ir.ui.view','source_id':view.id,'payload':{'xmlid':'hr_payroll.report_payslip','arch':view.arch_db}})
    tools.convert_file(env,'hr_payroll','views/report_payslip_templates.xml',{},mode='update',noupdate=False,kind='data')
    assert 'worked_days_table' in view.arch_db
    env.cr.commit()
print('PAYROLL_NATIVE_REPORT_OK')
