"""Translated original notes and one scalar input-name plan, never master writes."""
from odoo import _, fields, models
from odoo.exceptions import ValidationError
from psycopg2 import sql

from ..translation_storage import TranslationStorageError, original_input_name_literal, original_translation_payload


def _prepare_record_translation(record, field_name, original):
    record.ensure_one()
    if (record._name, field_name) != ("hr.salary.rule", "note"):
        raise ValidationError(_("Original translation preparation is limited to payroll configuration masters."))
    record.check_access("read")
    record.check_field_access_rights("read", [field_name])
    if type(record.id) is not int or record.id <= 0:
        raise ValidationError(_("Save the original payroll configuration master before preparing translations."))
    record.flush_recordset([field_name])
    record.env.cr.execute(sql.SQL("SELECT {} FROM {} WHERE id=%s").format(
        sql.Identifier(field_name), sql.Identifier(record._table)), (record.id,))
    found = record.env.cr.fetchone()
    if found is None:
        raise ValidationError(_("The original payroll configuration master is missing."))
    try:
        return original_translation_payload(original, existing=found[0])
    except TranslationStorageError:
        raise ValidationError(_("Original payroll translations require a lossless, nonconflicting base-language projection.")) from None


class SalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    note = fields.Html(translate=True)

    def _step_original_note_translations(self, original):
        """Return a checked import plan; never write the rule or evaluate it."""
        return _prepare_record_translation(self, "note", original)


class InputType(models.Model):
    _inherit = "hr.payslip.input.type"

    name = fields.Char(translate=False)

    def _step_original_name_literal(self, original):
        """Return a checked scalar plan; never write a master or choose a language."""
        normal = self.sudo(False)
        normal.ensure_one()
        if normal._name != "hr.payslip.input.type":
            raise ValidationError(_("Original literal-name preparation is limited to payroll input types."))
        normal.check_access("read")
        normal.check_field_access_rights("read", ["name"])
        if type(normal.id) is not int or normal.id <= 0:
            raise ValidationError(_("Save the original input type before preparing its literal name."))
        normal.flush_recordset(["name"])
        normal.env.cr.execute("SELECT name FROM hr_payslip_input_type WHERE id=%s", (normal.id,))
        found = normal.env.cr.fetchone()
        if found is None:
            raise ValidationError(_("The original payroll input type is missing."))
        try:
            return original_input_name_literal(original, existing=found[0])
        except TranslationStorageError:
            raise ValidationError(_("Original input names require one unchanged literal without extra languages.")) from None

    def _step_original_name_translations(self, original):
        """Legacy planner alias: returns a scalar literal, never a translation map."""
        return self._step_original_name_literal(original)


class PayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    # OCA inherits rule fields into lines. Keep its existing historical TEXT
    # storage explicitly: this block adopts master notes only, never line notes.
    # Equivalence with any native historical representation remains a separate gate.
    note = fields.Html(translate=False)
