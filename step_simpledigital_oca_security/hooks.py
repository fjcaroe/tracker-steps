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


def post_init_hook(env):
    """Retain original rule IDs as aliases, with no change to formulas or categories."""
    native=env['ir.module.module'].search_count([('name','=','hr_payroll'),('state','=','installed')])
    if not native:return
    if not env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_PAYROLL_API_'):
        raise UserError('Native rule identity preparation is limited to private rehearsals.')
    structure=env.ref('l10n_cl_simpledigital_payroll.structure_chile')
    for code in ('BASIC','GROSS','NET'):
        rules=structure.with_context(active_test=False).rule_ids.filtered(lambda rule:rule.code==code and rule.active)
        if len(rules)!=1:raise UserError('Ambiguous original rule identity: '+code)
        name='chile_rule_'+code.lower()
        alias=env['ir.model.data'].search([('module','=','step_simpledigital_oca_security'),('name','=',name)])
        if alias:
            if alias.model!='hr.salary.rule' or alias.res_id!=rules.id:raise UserError('Conflicting original rule identity: '+code)
        else:env['ir.model.data'].create({'module':'step_simpledigital_oca_security','name':name,'model':'hr.salary.rule','res_id':rules.id,'noupdate':True})


def uninstall_hook(env):
    # These are aliases of user configuration, not records owned by this bridge.
    # Detach them before Odoo deletes module data; never delete the salary rules.
    aliases=env['ir.model.data'].search([('module','=','step_simpledigital_oca_security'),
        ('name','in',['chile_rule_basic','chile_rule_gross','chile_rule_net'])])
    for alias in aliases:
        if alias.model!='hr.salary.rule':raise UserError('Conflicting rule alias during retirement.')
        rule=env['hr.salary.rule'].browse(alias.res_id).exists()
        if rule and rule.code.lower()!=alias.name.removeprefix('chile_rule_'):
            raise UserError('Original rule identity changed; retirement requires review.')
    aliases.unlink()
