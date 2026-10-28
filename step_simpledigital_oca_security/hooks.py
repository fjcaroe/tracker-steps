"""Adopt aliases of existing model/group IDs on the native reference engine."""
from odoo.exceptions import UserError


def pre_init_hook(env):
    if env['ir.module.module'].search_count([('name','=','payroll'),('state','=','installed')]):
        return
    if not env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_PAYROLL_API_'):
        raise UserError('Native identity preparation is limited to private Cerro rehearsals.')
    pairs={'model_'+name:'hr_payroll.model_'+name for name in ('hr_payslip','hr_payslip_line','hr_payslip_input','hr_payslip_worked_days')}
    pairs.update(group_payroll_user='hr_payroll.group_hr_payroll_user',group_payroll_manager='hr_payroll.group_hr_payroll_manager')
    for name,original in pairs.items():
        record=env.ref(original)
        alias=env['ir.model.data'].search([('module','=','payroll'),('name','=',name)])
        if alias:
            if alias.model!=record._name or alias.res_id!=record.id:
                raise UserError('Conflicting payroll identity alias: '+name)
        else:
            env['ir.model.data'].create({'module':'payroll','name':name,'model':record._name,'res_id':record.id,'noupdate':True})
