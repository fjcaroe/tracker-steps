"""Adopt original operational metadata before the payroll bridge is updated."""
from odoo.exceptions import UserError
from .ownership import FIELDS, RECORDS

LEGACY = 'step_hr'
CORE = 'step_operations_core'


def _owned(record):
    if record.name in RECORDS:
        if record.model != RECORDS[record.name]:
            raise UserError('Modelo incompatible para el identificador operacional %s.' % record.name)
        if record.model == 'ir.model.fields':
            field = record.env[record.model].browse(record.res_id).exists()
            if not field or field.name not in FIELDS.get(field.model, ()):
                raise UserError('Campo operacional incompatible: %s.' % record.name)
        return True
    if record.model == 'ir.model.fields.selection':
        selection = record.env[record.model].browse(record.res_id).exists()
        return bool(selection and selection.field_id.name in FIELDS.get(selection.field_id.model, ()))
    return False


def _alias(record, namespace):
    data = record.env['ir.model.data']
    existing = data.search([('module', '=', namespace), ('name', '=', record.name)])
    if existing:
        if len(existing) != 1 or (existing.model, existing.res_id) != (record.model, record.res_id):
            raise UserError('Identificador operacional en conflicto: %s.%s' % (namespace, record.name))
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
