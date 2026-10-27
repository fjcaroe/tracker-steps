"""Adopt original labor metadata, without copying business records or grants."""
from odoo.exceptions import UserError
from .ownership import MODELS, FIELDS, RECORDS, PAYROLL_FIELDS, SEQUENCES, RELATIONS

LEGACY = 'step_hr'
CORE = 'step_labor_operations_core'


def _owned(record):
    if record.name in RECORDS:
        if record.model != RECORDS[record.name] or not record.env[record.model].browse(record.res_id).exists():
            raise UserError('Identificador operacional incompatible: %s.' % record.name)
        if record.model == 'ir.model.fields':
            field = record.env[record.model].browse(record.res_id)
            if field.name not in FIELDS.get(field.model, ()):
                raise UserError('Campo operacional incompatible: %s.' % record.name)
        return True
    if record.model == 'ir.model.fields':
        field = record.env[record.model].browse(record.res_id).exists()
        return bool(field and field.model in MODELS and not (
            field.model == 'hr.salary.custom' and field.name in PAYROLL_FIELDS))
    if record.model == 'ir.model.fields.selection':
        selection = record.env[record.model].browse(record.res_id).exists()
        return bool(selection and selection.field_id.name in FIELDS.get(selection.field_id.model, ()))
    return False


def _alias(record, namespace):
    data = record.env['ir.model.data']
    existing = data.search([('module', '=', namespace), ('name', '=', record.name)])
    if existing:
        if len(existing) != 1 or (existing.model, existing.res_id) != (record.model, record.res_id):
            raise UserError('Identificador operacional en conflicto: %s.%s' % (namespace,record.name))
    else:
        data.create({'module':namespace,'name':record.name,'model':record.model,
                     'res_id':record.res_id,'noupdate':True if record.model == 'ir.sequence' else
                     record.noupdate if namespace == CORE else True})


def adopt_legacy_records(env):
    module = env['ir.module.module'].search([('name', '=', CORE)])
    old = env['ir.module.module'].search([('name', '=', LEGACY)])
    assert len(module) == 1
    relations = env['ir.model.relation'].search([('name', 'in', RELATIONS), ('module', 'in', old.ids)])
    # Before _reflect_relation runs, transfer the original metadata rows.
    # This preserves IDs and prevents the old module owning their SQL tables.
    relations.write({'module': module.id})
    for record in env['ir.model.data'].search([('module', '=', LEGACY)]):
        if _owned(record):
            _alias(record, CORE)
            record.noupdate = True


def preserve_legacy_xmlids(env):
    # XML init writes existing records even with noupdate. Only create missing
    # sequences here; preserve customized prefixes, counters and date ranges.
    for name, values in SEQUENCES.items():
        if not env.ref(CORE + '.' + name, raise_if_not_found=False):
            sequence = env['ir.sequence'].create(values)
            env['ir.model.data'].create({'module':CORE,'name':name,'model':'ir.sequence',
                                         'res_id':sequence.id,'noupdate':True})
    for record in env['ir.model.data'].search([('module', '=', CORE)]):
        if _owned(record):
            _alias(record, LEGACY)
    if env.ref(LEGACY + '.menu_step_hr_root', raise_if_not_found=False):
        env.ref(CORE + '.menu_labor_operations').active = False
