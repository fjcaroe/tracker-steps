"""Vista previa transitoria antes de generar/regenerar las líneas de una
Orden de Producción (Corte 2). Mismo contrato que
`wizard/plan_weekly_preview.py` (R1): calcula sin escribir, guarda una
huella determinista y `action_confirm()` sólo aplica si nada cambió desde
que se abrió."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StepManagementProductionOrderPreviewWizard(models.TransientModel):
    _name = "step.management.production.order.preview.wizard"
    _description = "Vista previa de generación de la Orden de Producción"

    order_id = fields.Many2one(
        "step.management.production.order", string="Orden de Producción",
        required=True, ondelete="cascade",
    )
    fingerprint = fields.Char(string="Huella", readonly=True)
    monday = fields.Date(string="Inicio (lunes)", readonly=True)
    sunday = fields.Date(string="Término (domingo)", readonly=True)
    remove_count = fields.Integer(string="Líneas actuales a reemplazar", readonly=True)
    add_count = fields.Integer(string="Líneas nuevas a crear", readonly=True)
    preview_line_ids = fields.One2many(
        "step.management.production.order.preview.wizard.line", "wizard_id",
        string="Detalle", readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order_id = res.get("order_id") or self.env.context.get("default_order_id")
        if order_id and "preview_line_ids" in (fields_list or []):
            order = self.env["step.management.production.order"].browse(order_id)
            commands, monday, sunday, fingerprint = order._build_op_commands()
            res["fingerprint"] = fingerprint
            res["monday"] = monday
            res["sunday"] = sunday
            res["remove_count"] = len(order.line_ids)
            res["add_count"] = len(commands)
            res["preview_line_ids"] = [
                (0, 0, {
                    "source_type": vals["source_type"],
                    "description": vals["description"],
                    "activity": vals["activity"],
                    "product_id": vals["product_id"],
                    "uom_id": vals["uom_id"],
                    "quantity": vals["quantity"],
                })
                for (_op, _zero, vals) in commands
            ]
        return res

    def action_confirm(self):
        self.ensure_one()
        commands, monday, sunday, fingerprint = self.order_id._build_op_commands()
        if fingerprint != self.fingerprint:
            raise UserError(_(
                "Las fuentes cambiaron desde que se abrió esta vista previa. "
                "Ábrala nuevamente antes de confirmar."
            ))
        self.order_id._apply_op_commands(commands, monday, sunday, fingerprint)
        return {
            "type": "ir.actions.act_window",
            "res_model": "step.management.production.order",
            "res_id": self.order_id.id, "view_mode": "form", "target": "current",
        }


class StepManagementProductionOrderPreviewWizardLine(models.TransientModel):
    _name = "step.management.production.order.preview.wizard.line"
    _description = "Detalle de la vista previa de la Orden de Producción"
    _order = "source_type, id"

    wizard_id = fields.Many2one(
        "step.management.production.order.preview.wizard", ondelete="cascade",
    )
    source_type = fields.Selection(
        [("plan_line", "Tarea planificada"),
         ("program_application", "Fitosanitario / Fertilización"),
         ("harvest_line", "Cosecha")],
        string="Origen",
    )
    description = fields.Char(string="Descripción")
    activity = fields.Char(string="Actividad")
    product_id = fields.Many2one("product.product", string="Producto / labor")
    uom_id = fields.Many2one("uom.uom", string="UdM")
    quantity = fields.Float(string="Cantidad", digits=(16, 4))
