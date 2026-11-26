from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    # SyS did not store the journal on its historical batches.
    journal_id = fields.Many2one(
        required=False,
        default=None,
        ondelete="restrict",
        check_company=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        batches = super().create(vals_list)
        if any(not batch.journal_id for batch in batches):
            raise ValidationError(_("Select a salary journal for the new payroll batch."))
        return batches

    def write(self, vals):
        if self and "journal_id" in vals and not vals["journal_id"]:
            raise ValidationError(_("The salary journal cannot be cleared."))
        return super().write(vals)

    @api.constrains("journal_id", "company_id")
    def _check_salary_journal_company(self):
        self._check_company(["journal_id"])
