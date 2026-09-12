"""Vista previa transitoria antes de regenerar tareas semanales (Corte 1
post Fase 6, respuesta del cliente: nunca borrar/recrear tareas automáticas
sin mostrar antes qué cambia). Las tareas manuales (`generated=False`) nunca
se tocan por este flujo."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StepManagementPlanWeeklyPreviewWizard(models.TransientModel):
    _name = "step.management.plan.weekly.preview.wizard"
    _description = "Vista previa de regeneración de tareas semanales"

    plan_id = fields.Many2one(
        "step.management.plan", string="Plan", required=True, ondelete="cascade",
    )
    fingerprint = fields.Char(
        string="Huella", readonly=True,
        help="Huella determinista de la fuente y los comandos mostrados "
             "(R1). Al confirmar se recalcula y compara: si el presupuesto "
             "o el plan cambiaron mientras tanto, no se escribe nada.",
    )
    season = fields.Char(string="Temporada", readonly=True)
    remove_count = fields.Integer(
        string="Tareas generadas a eliminar", readonly=True,
    )
    add_count = fields.Integer(string="Tareas nuevas a crear", readonly=True)
    keep_manual_count = fields.Integer(
        string="Tareas manuales que se conservan", readonly=True,
    )
    preview_line_ids = fields.One2many(
        "step.management.plan.weekly.preview.wizard.line", "wizard_id",
        string="Detalle de las tareas nuevas", readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        plan_id = res.get("plan_id") or self.env.context.get("default_plan_id")
        if plan_id and "preview_line_ids" in (fields_list or []):
            plan = self.env["step.management.plan"].browse(plan_id)
            commands, season = plan._build_weekly_task_commands()
            res["season"] = season
            res["fingerprint"] = plan._weekly_task_fingerprint(commands, season)
            res["remove_count"] = len(plan.line_ids.filtered("generated"))
            res["add_count"] = len(commands)
            res["keep_manual_count"] = len(
                plan.line_ids.filtered(lambda line: not line.generated)
            )
            res["preview_line_ids"] = [
                (0, 0, {
                    "date": vals["date"],
                    "center_id": vals["center_id"],
                    "indicator": vals["indicator"],
                    "quantity": vals["quantity"],
                    "uom_id": vals["uom_id"],
                    "week_label": vals["week_label"],
                })
                for (_op, _zero, vals) in commands
            ]
        return res

    def action_confirm(self):
        self.ensure_one()
        commands, season = self.plan_id._build_weekly_task_commands()
        fingerprint = self.plan_id._weekly_task_fingerprint(commands, season)
        if fingerprint != self.fingerprint:
            raise UserError(_(
                "El presupuesto o el plan cambiaron desde que se abrió esta "
                "vista previa. Ábrala nuevamente antes de confirmar."
            ))
        self.plan_id._apply_weekly_task_commands(commands, season)
        return {
            "type": "ir.actions.act_window",
            "res_model": "step.management.plan",
            "res_id": self.plan_id.id,
            "view_mode": "form",
            "target": "current",
        }


class StepManagementPlanWeeklyPreviewWizardLine(models.TransientModel):
    _name = "step.management.plan.weekly.preview.wizard.line"
    _description = "Detalle de la vista previa de tareas semanales"
    _order = "date, id"

    wizard_id = fields.Many2one(
        "step.management.plan.weekly.preview.wizard", ondelete="cascade",
    )
    date = fields.Date(string="Fecha")
    center_id = fields.Many2one("step.management.cost.center", string="Centro de costo")
    indicator = fields.Char(string="Tarea / indicador")
    quantity = fields.Float(string="Cantidad", digits=(16, 4))
    uom_id = fields.Many2one("uom.uom", string="UdM")
    week_label = fields.Char(string="Semana")
