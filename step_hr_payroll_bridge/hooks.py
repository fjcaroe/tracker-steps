"""Preserve original HR aliases while loading the optional real payroll bridge."""
from odoo.exceptions import UserError

CORE = 'step_hr_payroll_bridge'
FIELDS = {'hr.payslip': ('net_liquido',),
          'hr.salary.custom': ('payslip_run_id', 'struct_id'),
          'res.partner': ('duplicate_bank_partner_ids',)}
VIEWS = ('view_salary_payroll_bridge', 'view_tarja_payroll_bridge',
         'hr_payslip_step_view_tree', 'step_view_res_partner_map')


def owned(env, row):
    if row.name in VIEWS and row.model != 'ir.ui.view':
        raise UserError('Vista HR con modelo incompatible: %s' % row.name)
    if row.model not in ('ir.ui.view', 'ir.model', 'ir.model.fields'):
        return False
    record = env[row.model].browse(row.res_id).exists()
    if not record:
        return False
    if row.model == 'ir.ui.view':
        return row.name in VIEWS
    if row.model == 'ir.model':
        return record.model in FIELDS or record.model == 'step.tarja'
    if row.model == 'ir.model.fields':
        return (record.name in FIELDS.get(record.model, ()) or
                record.model == 'res.users' and record.name == 'duplicate_bank_partner_ids'
                and record.related == 'partner_id.duplicate_bank_partner_ids')
    return False


def alias(env, row, namespace):
    existing = env['ir.model.data'].search([('module', '=', namespace), ('name', '=', row.name)])
    if existing:
        if len(existing) != 1 or (existing.model, existing.res_id) != (row.model, row.res_id):
            raise UserError('Conflicto de identificador HR: %s.%s' % (namespace, row.name))
    else:
        env['ir.model.data'].create({'module': namespace, 'name': row.name,
            'model': row.model, 'res_id': row.res_id,
            'noupdate': True if row.model != 'ir.ui.view' or namespace == 'step_hr' else row.noupdate})


def pre_init_hook(env):
    for row in env['ir.model.data'].search([('module', '=', 'step_hr')]):
        if owned(env, row):
            alias(env, row, CORE)
            row.noupdate = True


def post_init_hook(env):
    for row in env['ir.model.data'].search([('module', '=', CORE)]):
        if owned(env, row):
            alias(env, row, 'step_hr')
