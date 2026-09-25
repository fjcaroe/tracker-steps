from odoo import fields, models


class StepManagementBudgetReopenWizard(models.TransientModel):
    _name = "step.management.budget.reopen.wizard"
    _description = "Creación trazable de una corrección presupuestaria"

    budget_id = fields.Many2one(
        "step.management.operational.budget", string="Presupuesto", required=True,
        ondelete="cascade",
    )
    reason = fields.Text(string="Motivo de la corrección", required=True)

    def action_confirm(self):
        self.ensure_one()
        revision = self.budget_id._do_reopen(self.reason)
        return {
            "type": "ir.actions.act_window",
            "res_model": "step.management.operational.budget",
            "res_id": revision.id,
            "view_mode": "form",
            "target": "current",
        }
