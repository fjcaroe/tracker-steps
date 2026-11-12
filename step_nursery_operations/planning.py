from collections import defaultdict
from datetime import timedelta
from math import ceil

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class NurseryCycle(models.Model):
    _name = "step.nursery.cycle"
    _description = "Parámetros de siembra por especie y temporada"
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    species_id = fields.Many2one("step.especie", required=True, check_company=True, ondelete="restrict")
    season_id = fields.Many2one("step.temporada", required=True, check_company=True, ondelete="restrict")
    cycle_days = fields.Integer(required=True)
    extra_pct = fields.Float(string="Sobresiembra (%)", required=True, digits=(8, 2))
    tray_id = fields.Many2one("product.product", string="Bandeja retornable", required=True,
                              check_company=True, ondelete="restrict")
    cells_per_tray = fields.Integer(string="Cavidades por bandeja", required=True)
    _sql_constraints = [
        ("cycle_key", "UNIQUE(company_id, species_id, season_id)",
         "Ya hay parámetros para esta especie y temporada."),
        ("cycle_bounds", "CHECK(cycle_days > 0 AND cells_per_tray > 0 AND extra_pct BETWEEN 0 AND 100)",
         "El ciclo y las cavidades deben ser positivos; la sobre-siembra debe estar entre 0 y 100 %."),
    ]


class NurseryPlan(models.Model):
    _name = "step.nursery.plan"
    _description = "Plan de siembra por línea de venta"
    _rec_name = "sale_line_id"
    _order = "sowing_at, id"
    _check_company_auto = True

    sale_line_id = fields.Many2one("sale.order.line", string="Línea de venta", required=True,
                                    check_company=True, ondelete="restrict", index=True)
    company_id = fields.Many2one(related="sale_line_id.company_id", store=True, index=True)
    product_id = fields.Many2one(related="sale_line_id.product_id")
    partner_id = fields.Many2one(related="sale_line_id.order_id.partner_id")
    cycle_id = fields.Many2one("step.nursery.cycle", string="Ciclo de siembra", required=True,
                               check_company=True, ondelete="restrict")
    promised_at = fields.Datetime(string="Entrega comprometida", required=True)
    sowing_at = fields.Datetime(string="Siembra calculada", compute="_compute_targets", store=True)
    promised_units = fields.Integer(string="Plantines vendidos", compute="_compute_targets", store=True)
    sowing_units = fields.Integer(string="Plantines a sembrar", compute="_compute_targets", store=True)
    tray_count = fields.Integer(string="Bandejas previstas", compute="_compute_targets", store=True)
    bom_id = fields.Many2one("mrp.bom", string="Receta", required=True, check_company=True, ondelete="restrict")
    production_id = fields.Many2one("mrp.production", string="Orden de producción",
                                     check_company=True, ondelete="restrict", readonly=True, copy=False)
    slot_ids = fields.One2many("step.nursery.slot", "plan_id", string="Ocupación por etapa")
    _sql_constraints = [
        ("sale_line_key", "UNIQUE(sale_line_id)", "Esta línea ya tiene un plan de siembra."),
    ]

    @api.onchange("sale_line_id")
    def _onchange_sale_line(self):
        self.promised_at = self.sale_line_id.order_id.commitment_date or False

    @api.depends("sale_line_id.product_uom_qty", "sale_line_id.product_uom",
                 "promised_at", "cycle_id.cycle_days", "cycle_id.extra_pct", "cycle_id.cells_per_tray")
    def _compute_targets(self):
        unit = self.env.ref("uom.product_uom_unit")
        for plan in self:
            plan.sowing_at = plan.promised_at - timedelta(days=plan.cycle_id.cycle_days) if plan.promised_at else False
            ordered = 0
            if plan.sale_line_id.product_uom.category_id == unit.category_id:
                ordered = plan.sale_line_id.product_uom._compute_quantity(
                    plan.sale_line_id.product_uom_qty, unit, round=False)
            plan.promised_units = ceil(round(max(0, ordered), 6))
            required = ceil(round(plan.promised_units * (1 + plan.cycle_id.extra_pct / 100), 6))
            plan.tray_count = ceil(required / plan.cycle_id.cells_per_tray) if plan.cycle_id.cells_per_tray else 0
            plan.sowing_units = plan.tray_count * plan.cycle_id.cells_per_tray

    @api.constrains("sale_line_id", "cycle_id", "bom_id", "promised_at")
    def _check_recipe(self):
        unit = self.env.ref("uom.product_uom_unit")
        for plan in self:
            if (not plan.product_id or plan.sale_line_id.display_type
                    or plan.sale_line_id.product_uom.category_id != unit.category_id
                    or plan.sale_line_id.product_uom_qty <= 0):
                raise ValidationError(_("Seleccione una línea de plantines con cantidad positiva en unidades."))
            if (plan.bom_id.type != "normal" or plan.bom_id.product_tmpl_id != plan.product_id.product_tmpl_id
                    or (plan.bom_id.product_id and plan.bom_id.product_id != plan.product_id)):
                raise ValidationError(_("La receta debe fabricar el producto de la línea de venta."))

    def action_create_production(self):
        self.ensure_one()
        self.check_access("write")
        self.env.cr.execute("SELECT id FROM step_nursery_plan WHERE id = %s FOR UPDATE", (self.id,))
        self.invalidate_recordset(["production_id"])
        if self.production_id:
            return self._production_action()
        if self.sale_line_id.order_id.state != "sale":
            raise UserError(_("Confirme el pedido antes de crear la orden de siembra."))
        self._check_recipe()
        if not self.sowing_units or not self.sowing_at:
            raise UserError(_("Revise el ciclo, las unidades y la fecha de entrega."))
        unit = self.env.ref("uom.product_uom_unit")
        order = self.sale_line_id.order_id
        picking_type = order.warehouse_id.manu_type_id
        if not picking_type:
            raise UserError(_("Configure un tipo de fabricación en la bodega del pedido."))
        native = self.env["mrp.production"].with_company(self.company_id).create({
            "company_id": self.company_id.id,
            "product_id": self.product_id.id,
            "product_uom_id": self.product_id.uom_id.id,
            "product_qty": unit._compute_quantity(self.sowing_units, self.product_id.uom_id, round=False),
            "bom_id": self.bom_id.id,
            "picking_type_id": picking_type.id,
            "origin": order.name,
            "date_start": self.sowing_at,
            "date_deadline": self.promised_at,
        })
        self.production_id = native
        return self._production_action()

    def _production_action(self):
        self.production_id.check_access("read")
        return {"type": "ir.actions.act_window", "name": _("Orden de siembra"),
                "res_model": "mrp.production", "res_id": self.production_id.id,
                "view_mode": "form", "target": "current"}


class StockLocation(models.Model):
    _inherit = "stock.location"

    step_nursery_tray_capacity = fields.Integer(string="Capacidad de vivero (bandejas)")
    _sql_constraints = [
        ("step_nursery_nonnegative_capacity", "CHECK(step_nursery_tray_capacity >= 0)",
         "La capacidad de bandejas no puede ser negativa."),
    ]


class NurserySlot(models.Model):
    _name = "step.nursery.slot"
    _description = "Ocupación prevista de vivero"
    _rec_name = "location_id"
    _order = "start_date, location_id, id"
    _check_company_auto = True

    plan_id = fields.Many2one("step.nursery.plan", string="Siembra", required=True, ondelete="cascade",
                              check_company=True, index=True)
    company_id = fields.Many2one(related="plan_id.company_id", store=True, index=True)
    location_id = fields.Many2one("stock.location", string="Nave o mesón", required=True,
                                   check_company=True, ondelete="restrict", index=True)
    operation_id = fields.Many2one("mrp.routing.workcenter", string="Etapa de la receta", ondelete="restrict")
    start_date = fields.Date(string="Inicio", required=True)
    end_date = fields.Date(string="Término inclusive", required=True)
    trays = fields.Integer(string="Bandejas", required=True)
    peak_trays = fields.Integer(string="Ocupación máxima en el intervalo", compute="_compute_peak")
    over_capacity = fields.Boolean(string="Sobrecupo", compute="_compute_peak")
    _sql_constraints = [
        ("slot_values", "CHECK(start_date <= end_date AND trays > 0)",
         "Indique un intervalo válido y una cantidad positiva de bandejas."),
    ]

    @api.constrains("operation_id", "location_id", "plan_id")
    def _check_stage(self):
        for slot in self:
            if slot.location_id.usage != "internal" or not slot.location_id.step_nursery_tray_capacity:
                raise ValidationError(_("La ubicación debe ser interna y tener capacidad de bandejas configurada."))
            if slot.operation_id and slot.operation_id.bom_id != slot.plan_id.bom_id:
                raise ValidationError(_("Seleccione una etapa de la receta de este plan."))

    def _compute_peak(self):
        for slot in self:
            slot.peak_trays = 0
            slot.over_capacity = False
            if not slot.location_id or not slot.start_date or not slot.end_date or not slot.company_id:
                continue
            others = self.search([
                ("id", "!=", slot._origin.id), ("company_id", "=", slot.company_id.id),
                ("location_id", "=", slot.location_id.id), ("start_date", "<=", slot.end_date),
                ("end_date", ">=", slot.start_date), ("plan_id.sale_line_id.order_id.state", "!=", "cancel"),
                "|", ("plan_id.production_id", "=", False),
                ("plan_id.production_id.state", "not in", ["cancel", "done"]),
            ])
            events = defaultdict(int)
            for start, end, trays in [(r.start_date, r.end_date, r.trays) for r in others] + [
                (slot.start_date, slot.end_date, slot.trays),
            ]:
                events[max(start, slot.start_date)] += trays
                if end < slot.end_date:
                    events[end + timedelta(days=1)] -= trays
            running = peak = 0
            for day in sorted(events):
                running += events[day]
                peak = max(peak, running)
            slot.peak_trays = peak
            slot.over_capacity = peak > slot.location_id.step_nursery_tray_capacity
