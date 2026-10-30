"""Retain original scalar/nullable storage without rewriting historical rows.

The pinned free-engine overlay must use the same declarations before its first
initialization. These adapter fields keep that contract through later upgrades;
they do not convert JSONB, select a language, infer attendance or compute pay.
"""
from psycopg2 import sql

from odoo import _, fields, models
from odoo.exceptions import UserError


def _admit_literal_line_storage(cr, table):
    # Metadata only: an existing translated line cannot be collapsed to one
    # language merely by installing this adapter. The runner makes the same
    # admission before the earlier OCA initialization in a derived overlay.
    cr.execute("SELECT t.typname FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid "
        "WHERE a.attrelid=to_regclass(%s) AND a.attname='name' AND NOT a.attisdropped", (table,))
    found = cr.fetchone()
    if found and found != ('varchar',):
        raise UserError(_("Original payroll line names require unchanged scalar storage; translated historical lines need a separate migration."))
    if found:
        cr.execute(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} WHERE name IS NULL)').format(sql.Identifier(table)))
        if cr.fetchone()[0]:
            raise UserError(_("Original payroll line names contain missing literals; no historical value was inferred."))


class Contract(models.Model):
    _inherit = 'hr.contract'

    resource_calendar_id = fields.Many2one(required=False, ondelete='set null')


class WorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    name = fields.Char(required=False)


class PayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    # A stored payslip line is an original literal, independently of the
    # translated rule master inherited by the actual OCA model.
    name = fields.Char(required=True, translate=False)

    def _auto_init(self):
        _admit_literal_line_storage(self.env.cr, self._table)
        return super()._auto_init()
