from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HistoricalFieldsMixin:
    """Existing rows can carry unknown values. New OCA rows need all of them."""

    @api.model_create_multi
    def create(self, vals_list):
        # Typed inputs and days obtain their codes inside the provider's create.
        # Validate the final values, including all rows in a single batch.
        with self.env.cr.savepoint():
            rows = super().create(vals_list)
            for row in rows:
                if any(not row[name] for name in self._sys_history_fields):
                    raise ValidationError(_("New payroll rows require their codes and calculation settings."))
        return rows

    def write(self, values):
        if any(name in values and not values[name] for name in self._sys_history_fields):
            raise ValidationError(_("A payroll code or calculation setting cannot be cleared."))
        return super().write(values)


class PayslipInput(HistoricalFieldsMixin, models.Model):
    _inherit = "hr.payslip.input"
    _sys_history_fields = ("code",)

    code = fields.Char(required=False)


class PayslipWorkedDays(HistoricalFieldsMixin, models.Model):
    _inherit = "hr.payslip.worked_days"
    _sys_history_fields = ("code",)

    code = fields.Char(required=False)


class PayslipLine(HistoricalFieldsMixin, models.Model):
    _inherit = "hr.payslip.line"
    _sys_history_fields = ("amount_select", "condition_select", "condition_python")

    # A field default is also used by Odoo when it initializes a new column.
    # Apply the OCA create defaults only to new rows through default_get.
    amount_select = fields.Selection(required=False, default=None)
    condition_select = fields.Selection(required=False, default=None)
    condition_python = fields.Text(required=False, default=None)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        rule_fields = self.env["hr.salary.rule"]._fields
        for name in self._sys_history_fields:
            if name in fields_list and name not in values and rule_fields[name].default:
                values[name] = rule_fields[name].default(self)
        return values
