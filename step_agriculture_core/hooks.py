"""Transfer ownership while keeping the original records and public XML IDs."""
from odoo.exceptions import UserError

from .ownership import MODELS, FIELDS, RECORDS

LEGACY = 'step_hr'
CORE = 'step_agriculture_core'


def _owned(record):
    if record.name in RECORDS:
        if record.model != RECORDS[record.name]:
            raise UserError('Identificador agrícola con modelo inesperado: %s' % record.name)
        if record.model == 'ir.model.fields':
            field = record.env[record.model].browse(record.res_id).exists()
            if not field or field.name not in FIELDS.get(field.model, ()):
                raise UserError('Campo agrícola incompatible: %s' % record.name)
        return True
    # Odoo also generates inherited fields and selection XML IDs. Protect
    # those owned by these models when the old payroll bridge is retired.
    if record.model == 'ir.model.fields':
        return record.env[record.model].browse(record.res_id).exists().model in MODELS
    if record.model == 'ir.model.fields.selection':
        selection = record.env[record.model].browse(record.res_id).exists()
        return bool(selection and selection.field_id.model in FIELDS and
                    selection.field_id.name in FIELDS[selection.field_id.model])
    return False


def _alias(record, namespace):
    data = record.env['ir.model.data']
    existing = data.search([('module', '=', namespace), ('name', '=', record.name)])
    if existing:
        if len(existing) != 1 or (existing.model, existing.res_id) != (record.model, record.res_id):
            raise UserError('Identificador agrícola en conflicto: %s.%s' % (namespace, record.name))
    else:
        data.create({'module': namespace, 'name': record.name, 'model': record.model,
                     'res_id': record.res_id, 'noupdate': record.noupdate if namespace == CORE else True})


def adopt_legacy_records(env):
    for record in env['ir.model.data'].search([('module', '=', LEGACY)]):
        if _owned(record):
            _alias(record, CORE)
            record.noupdate = True


def preserve_legacy_xmlids(env):
    for record in env['ir.model.data'].search([('module', '=', CORE)]):
        if _owned(record):
            _alias(record, LEGACY)
    if env.ref(LEGACY + '.menu_step_hr_root', raise_if_not_found=False):
        # Existing destinations keep their original menu restrictions, including
        # optional agricultural-access groups on ancestor menus. Do not expose
        # a new shortcut around them. Standalone Community uses the new root.
        env.ref(CORE + '.menu_agriculture_core').active = False
    action = env.ref(CORE + '.action_step_centro_costo_analytic')
    # Do not use the old destructive (5, 0, 0) XML command: existing ordered
    # action-view records keep their IDs. Fresh Community gets the same views.
    if not action.view_ids:
        action.write({'view_ids': [(0, 0, {'view_mode': mode, 'view_id': env.ref(CORE + '.' + name).id})
                                  for mode, name in [('list', 'step_view_account_analytic_account_list'),
                                                     ('form', 'step_view_account_analytic_account_form')]]})
