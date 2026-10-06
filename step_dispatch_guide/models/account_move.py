from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    dispatch_guide_ids = fields.One2many(
        "step.dispatch.guide", "invoice_id", string="Guías de despacho", readonly=True,
    )
    dispatch_guide_count = fields.Integer(compute="_compute_dispatch_guide_count")

    def _compute_dispatch_guide_count(self):
        for move in self:
            move.dispatch_guide_count = len(move.dispatch_guide_ids)

    def action_view_dispatch_guides(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Guías facturadas"),
            "res_model": "step.dispatch.guide", "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id)],
        }

    def unlink(self):
        # Una factura borrada libera sus guías para volver a facturarlas.
        self.sudo().dispatch_guide_ids.write({"invoice_id": False})
        return super().unlink()
