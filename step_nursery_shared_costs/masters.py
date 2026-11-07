from datetime import timedelta
from math import isfinite

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

OPERATION = object()
OPERATION_KEY = "_steps_cost_reallocation"


def last_closed_week(record):
    today = fields.Date.context_today(record)
    return today - timedelta(days=today.weekday() + 7)


class AnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    step_cost_pool = fields.Boolean(string="Supra centro de costo", copy=False)
    step_cost_parent_id = fields.Many2one(
        "account.analytic.account", string="Centro de costo padre",
        check_company=True, ondelete="restrict", index=True, copy=False,
        domain="[('step_cost_pool', '=', True), ('company_id', '=', company_id), ('plan_id', '=', plan_id)]",
    )
    step_cost_child_ids = fields.One2many(
        "account.analytic.account", "step_cost_parent_id", string="Centros hijos",
    )
    step_cost_rule_ids = fields.One2many(
        "step.nursery.cost.rule", "parent_id", string="Labores y drivers", copy=False,
    )

    @api.constrains("step_cost_pool", "step_cost_parent_id", "company_id", "plan_id", "active")
    def _check_step_cost_hierarchy(self):
        for account in self:
            if account.step_cost_pool and (account.step_cost_parent_id or not account.company_id):
                raise ValidationError(_("Un supra centro necesita empresa propia y no puede tener otro padre."))
            if account.step_cost_rule_ids and not account.step_cost_pool:
                raise ValidationError(_("Quite las reglas de reparto antes de cambiar el tipo del centro."))
            for child in (account | account.with_context(active_test=False).step_cost_child_ids):
                parent = child.step_cost_parent_id
                if parent and (
                    not parent.step_cost_pool or child.step_cost_pool or not child.company_id
                    or child.company_id != parent.company_id or child.plan_id != parent.plan_id
                    or (child.active and not parent.active)
                ):
                    raise ValidationError(_("El centro hijo y su padre activo deben pertenecer a la misma empresa y plan."))

    def write(self, vals):
        for field in ("company_id", "plan_id"):
            if field in vals:
                changed = self.filtered(lambda account: account[field].id != vals[field])
                if changed and self.env["step.nursery.cost.run"].sudo().search_count([
                    ("state", "!=", "draft"),
                    "|", ("parent_id", "in", changed.ids), ("line_ids.center_id", "in", changed.ids),
                ], limit=1):
                    raise ValidationError(_("Un centro con repartos históricos conserva su empresa y plan."))
        return super().write(vals)

    def action_step_cost_items(self):
        self.ensure_one()
        self.check_access("read")
        column = self.plan_id._column_name()
        return {
            "type": "ir.actions.act_window", "name": _("Movimientos de %s") % self.display_name,
            "res_model": "account.analytic.line", "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [(column, "=", self.id), ("company_id", "=", self.company_id.id)],
            "context": {f"default_{column}": self.id, "default_company_id": self.company_id.id,
                        "analytic_plan_id": self.plan_id.id},
        }


class CostRule(models.Model):
    _name = "step.nursery.cost.rule"
    _description = "Labor y driver del supra centro"
    _check_company_auto = True

    parent_id = fields.Many2one("account.analytic.account", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="parent_id.company_id", store=True, index=True)
    labor_id = fields.Many2one(
        "product.template", string="Labor", required=True, ondelete="restrict",
        check_company=True, domain="[('type', '=', 'service')]",
    )
    driver_id = fields.Many2one("step.sawmill.costing.driver", string="Driver", required=True,
                                ondelete="restrict", check_company=True)
    _sql_constraints = [("parent_labor_unique", "unique(parent_id, labor_id)", "La labor ya tiene driver en este centro.")]

    @api.constrains("parent_id", "labor_id", "driver_id")
    def _check_cost_rule(self):
        for rule in self:
            if not rule.parent_id.step_cost_pool or rule.labor_id.type != "service":
                raise ValidationError(_("Seleccione un supra centro y una labor del catálogo de servicios."))


class DriverMeasure(models.Model):
    _name = "step.nursery.cost.measure"
    _description = "Carga semanal del driver"
    _check_company_auto = True
    _order = "week_start desc, center_id, driver_id"

    center_id = fields.Many2one("account.analytic.account", string="Centro hijo", required=True,
                                ondelete="restrict", check_company=True,
                                domain="[('step_cost_parent_id', '!=', False), ('company_id', '=', company_id)]")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    driver_id = fields.Many2one("step.sawmill.costing.driver", string="Driver", required=True,
                                ondelete="restrict", check_company=True)
    week_start = fields.Date(string="Semana desde", required=True, default=last_closed_week, index=True)
    quantity = fields.Float(string="Cantidad semanal", required=True, digits=(16, 4))
    uom_id = fields.Many2one(related="driver_id.uom_id", string="Unidad")
    _sql_constraints = [("center_driver_week_unique", "unique(center_id, driver_id, week_start)",
                         "Ya existe una cantidad para ese centro, driver y semana.")]

    @api.constrains("week_start", "quantity", "center_id", "company_id")
    def _check_measure(self):
        for measure in self:
            if not measure.center_id.step_cost_parent_id or measure.center_id.company_id != measure.company_id:
                raise ValidationError(_("La medición requiere un centro hijo de la misma empresa."))
            if measure.week_start.weekday() != 0 or not isfinite(measure.quantity) or measure.quantity < 0:
                raise ValidationError(_("Ingrese el lunes de la semana y una cantidad igual o mayor que cero."))


class AnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    step_cost_labor_id = fields.Many2one(
        "product.template", string="Labor de reparto", check_company=True, ondelete="restrict",
        domain="[('type', '=', 'service')]",
    )
    step_cost_run_id = fields.Many2one("step.nursery.cost.run", string="Reparto semanal", index=True,
                                      ondelete="restrict", copy=False, check_company=True)
    step_cost_source_id = fields.Many2one("account.analytic.line", string="Cargo original", index=True,
                                         ondelete="set null", copy=False, check_company=True)
    step_cost_is_reversal = fields.Boolean(string="Reversa de reparto", copy=False)
    step_cost_active_run_id = fields.Many2one("step.nursery.cost.run", string="Cargo incluido en reparto",
                                             ondelete="restrict", copy=False, check_company=True)

    _step_cost_metadata = {"step_cost_run_id", "step_cost_source_id", "step_cost_is_reversal", "step_cost_active_run_id"}

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get(OPERATION_KEY) is not OPERATION:
            if any(self._step_cost_metadata & vals.keys() for vals in vals_list) or any(
                self.env.context.get(f"default_{field}") for field in self._step_cost_metadata
            ):
                raise AccessError(_("Genere los movimientos desde el reparto semanal."))
        return super().create(vals_list)

    def _check_step_cost_edit(self):
        if self.step_cost_run_id:
            raise UserError(_("Los movimientos del reparto se corrigen con la acción Revertir."))
        if self.step_cost_active_run_id:
            raise UserError(_("Revierta el reparto semanal antes de modificar un cargo incluido."))

    def write(self, vals):
        if self.env.context.get(OPERATION_KEY) is OPERATION and set(vals) == {"step_cost_active_run_id"}:
            return super().write(vals)
        if self._step_cost_metadata & vals.keys():
            raise AccessError(_("La trazabilidad del reparto se genera automáticamente."))
        source_fields = {"amount", "date", "company_id", "product_id", "step_cost_labor_id", "move_line_id",
                         "general_account_id", "auto_account_id", *self._get_plan_fnames()}
        if source_fields & vals.keys() or self.step_cost_run_id:
            self._check_step_cost_edit()
        return super().write(vals)

    def unlink(self):
        self._check_step_cost_edit()
        return super().unlink()


class MoveLine(models.Model):
    _inherit = "account.move.line"

    step_cost_labor_id = fields.Many2one(
        "product.template", string="Labor de reparto", check_company=True, ondelete="restrict",
        domain="[('type', '=', 'service')]",
    )

    def _prepare_analytic_lines(self):
        values = super()._prepare_analytic_lines()
        if self.step_cost_labor_id:
            for line in values:
                line["step_cost_labor_id"] = self.step_cost_labor_id.id
        return values

    def write(self, vals):
        if "step_cost_labor_id" in vals and self.filtered(
            lambda line: line.parent_state == "posted" and line.step_cost_labor_id.id != vals["step_cost_labor_id"]
        ):
            raise UserError(_("Clasifique el cargo analítico antes de repartir un documento ya contabilizado."))
        return super().write(vals)


class Company(models.Model):
    _inherit = "res.company"

    @api.model
    def get_steps_greenhouse_dashboard(self):
        result = super().get_steps_greenhouse_dashboard()
        result["shared_costs"] = self.env.user.has_group("account.group_account_user")
        return result
