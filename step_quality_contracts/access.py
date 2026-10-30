"""Complete physical-reference admission without elevating the normal actor."""
from psycopg2 import sql
from odoo import _
from odoo.exceptions import UserError


FINAL_STATES = ('success', 'failed')


def normal_read(records, names):
    normal = records.sudo(False)
    normal.check_access('read')
    normal.check_field_access_rights('read', names)
    return normal


def children(parents, model_name, inverse, names):
    """SQL discovers IDs only; every actual child must pass normal ACL first."""
    model = parents.env[model_name].sudo(False).with_context(active_test=False)
    normal_read(model, list(set(names) | {inverse}))
    parents.check_access('read')
    if any(type(ident) is not int for ident in parents.ids):
        raise UserError(_('Save the original quality references before operating their children.'))
    model.flush_model([inverse])
    model.env.cr.execute(sql.SQL('SELECT id FROM {} WHERE {}=ANY(%s) ORDER BY id').format(
        sql.Identifier(model._table), sql.Identifier(inverse)), (parents.ids,))
    return normal_read(model.browse([row[0] for row in model.env.cr.fetchall()]), names)


def mutable(records):
    normal = normal_read(records, ['state'])
    if any(record.state in FINAL_STATES for record in normal):
        raise UserError(_('Finalized quality evidence cannot be changed or reopened.'))
    return normal


def original_quality_provider(env):
    """No alternative model may be silently returned as native evidence."""
    if 'quality.check' not in env:
        raise UserError(_('The original quality.check provider is not adopted; no other inspection will replace its identity.'))
    return env['quality.check'].sudo(False)
