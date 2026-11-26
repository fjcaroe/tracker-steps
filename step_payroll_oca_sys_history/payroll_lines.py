from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HistoricalFieldsMixin:
    # Odoo replaces class bases during registry setup. Keep the recordset layout.
    __slots__ = ()

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
        for name, (parent, attribute) in self._sys_related_fields.items():
            if name not in values:
                continue
            for row in self:
                target = (self.env[self._fields[parent].comodel_name].browse(values[parent])
                          if parent in values else row[parent])
                expected = target[attribute] if target else False
                if self._fields[name].type == "many2one" and expected:
                    expected = expected.id
                if values[name] != expected:
                    raise ValidationError(_("A related payroll field must match its original linked record."))
        if self and any(name in values and not values[name] for name in self._sys_history_fields):
            raise ValidationError(_("A payroll code or calculation setting cannot be cleared."))
        return super().write(values)


class PayslipInput(HistoricalFieldsMixin, models.Model):
    _inherit = "hr.payslip.input"
    _sys_history_fields = ("code",)
    _sys_related_fields = {"code": ("input_type_id", "code"), "contract_id": ("payslip_id", "contract_id")}

    code = fields.Char(related="input_type_id.code", store=False, required=True, readonly=True, copy=False)
    contract_id = fields.Many2one(related="payslip_id.contract_id", store=False, required=True,
                                  readonly=True, copy=False)


class PayslipWorkedDays(HistoricalFieldsMixin, models.Model):
    _inherit = "hr.payslip.worked_days"
    _sys_history_fields = ("code",)
    _sys_related_fields = {"code": ("work_entry_type_id", "code"), "contract_id": ("payslip_id", "contract_id")}

    code = fields.Char(related="work_entry_type_id.code", store=False, required=False, readonly=True, copy=False)
    contract_id = fields.Many2one(related="payslip_id.contract_id", store=False, required=False,
                                  readonly=True, copy=False)


class PayslipLine(HistoricalFieldsMixin, models.Model):
    _inherit = "hr.payslip.line"
    _sys_history_fields = ("condition_select", "condition_python")
    _sys_related_fields = {"amount_select": ("salary_rule_id", "amount_select")}

    # A field default is also used by Odoo when it initializes a new column.
    # Apply the OCA create defaults only to new rows through default_get.
    amount_select = fields.Selection(related="salary_rule_id.amount_select", store=False,
                                     required=False, readonly=True, copy=False, default=None, index=False)
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


class Payslip(models.Model):
    _inherit = "hr.payslip"

    def compute_sheet(self):
        for slip in self.filtered(lambda s: s.state in ("draft", "verify")):
            # OCA indexes these rows by code and replaces calculated lines.
            # Stop before either operation could discard an unknown value.
            for rows in (slip.worked_days_line_ids, slip.input_line_ids, slip.line_ids):
                if any(not row[name] for row in rows for name in rows._sys_history_fields):
                    raise UserError(_("Review the missing historical payroll codes and settings before recalculating."))
        return super().compute_sheet()
