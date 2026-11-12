from math import isfinite

from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class NurseryBatchAllocation(models.Model):
    _name = "step.nursery.batch.allocation"
    _description = "Reparto de costos de centro a lotes de vivero"
    _rec_name = "run_id"
    _check_company_auto = True

    run_id = fields.Many2one("step.nursery.cost.run", string="Reparto semanal confirmado", required=True,
                              check_company=True, ondelete="restrict", domain="[('state', '=', 'done')]")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    center_id = fields.Many2one("account.analytic.account", string="Centro de costo", required=True,
                                 check_company=True, ondelete="restrict")
    line_ids = fields.One2many("step.nursery.batch.allocation.line", "allocation_id", string="Lotes y pesos")
    run_state = fields.Selection(related="run_id.state", string="Estado del reparto semanal")
    amount = fields.Monetary(string="Costo del centro a distribuir", compute="_compute_amount")
    _sql_constraints = [
        ("weekly_center", "UNIQUE(run_id, center_id)", "El centro ya tiene un reparto a lotes para esta semana."),
    ]

    @api.depends("run_id.line_ids.amount", "run_id.line_ids.center_id", "center_id", "run_state")
    def _compute_amount(self):
        for allocation in self:
            allocation.amount = sum(row.amount for row in allocation.run_id.line_ids
                                    if row.center_id == allocation.center_id) if allocation.run_state == "done" else 0

    @api.constrains("run_id", "center_id", "company_id")
    def _check_source(self):
        for allocation in self:
            if (allocation.run_state != "done" or allocation.run_id.company_id != allocation.company_id
                    or allocation.center_id not in allocation.run_id.line_ids.center_id):
                raise ValidationError(_("Seleccione un reparto confirmado que incluya este centro y empresa."))


class NurseryBatchAllocationLine(models.Model):
    _name = "step.nursery.batch.allocation.line"
    _description = "Participación de un lote en el reparto semanal de un centro"
    _rec_name = "production_id"
    _check_company_auto = True
    _order = "id"

    allocation_id = fields.Many2one("step.nursery.batch.allocation", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="allocation_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    production_id = fields.Many2one("mrp.production", string="Orden de siembra", required=True,
                                     check_company=True, ondelete="restrict", index=True)
    weight = fields.Float(string="Peso relativo", required=True, digits=(16, 4))
    amount = fields.Monetary(string="Costo asignado", compute="_compute_amount")
    _sql_constraints = [
        ("allocation_batch", "UNIQUE(allocation_id, production_id)", "El lote ya está incluido en este reparto."),
        ("positive_weight", "CHECK(weight > 0)", "El peso del lote debe ser mayor que cero."),
    ]

    @api.constrains("production_id", "weight")
    def _check_production(self):
        for line in self:
            if not isfinite(line.weight) or not line.production_id.step_nursery_plan_ids:
                raise ValidationError(_("Use una orden de siembra de vivero y un peso válido."))

    @api.depends("allocation_id.amount", "allocation_id.line_ids.weight", "weight")
    def _compute_amount(self):
        for row in self:
            peers = row.allocation_id.line_ids
            total = sum(peers.mapped("weight"))
            row.amount = 0
            if total and row in peers:
                before = sum(peers[:peers.ids.index(row.id)].mapped("weight"))
                currency = row.currency_id
                row.amount = (currency.round(row.allocation_id.amount * (before + row.weight) / total)
                              - currency.round(row.allocation_id.amount * before / total))


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    step_nursery_waste_kind = fields.Selection(
        [("normal", "Merma normal de vivero"), ("abnormal", "Merma anormal de vivero")],
        string="Tratamiento de merma")


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def action_step_nursery_batch_cost(self):
        self.ensure_one()
        self.check_access("read")
        if not self.env.user.has_group("account.group_account_user"):
            raise AccessError(_("La revisión del costo requiere permisos de Contabilidad."))
        if (self.state != "done" or not self.step_nursery_plan_ids or not self.lot_producing_id
                or self.move_byproduct_ids.filtered(lambda move: move.state == "done" and move.quantity)):
            raise UserError(_("Cierre una orden de vivero con un solo lote de salida y sin subproductos valorizados."))
        duplicates = self.search_count([
            ("company_id", "=", self.company_id.id), ("id", "!=", self.id), ("state", "=", "done"),
            ("product_id", "=", self.product_id.id), ("lot_producing_id", "=", self.lot_producing_id.id),
        ])
        if duplicates:
            raise UserError(_("Este lote tiene varias órdenes de origen. Separe los lotes antes de calcular el costo."))
        wizard = self.env["step.nursery.batch.cost.report"].create(self._step_nursery_cost_values())
        return {"type": "ir.actions.act_window", "name": _("Costo real de lote"),
                "res_model": wizard._name, "res_id": wizard.id, "view_mode": "form", "target": "new"}

    def _step_nursery_cost_values(self):
        self.ensure_one()
        native = self.with_company(self.company_id)
        unit = self.env.ref("uom.product_uom_unit")
        currency = native.company_id.currency_id
        finished = native.move_finished_ids.filtered(lambda move: move.state == "done" and move.product_id == native.product_id)
        produced = sum(m.product_uom._compute_quantity(m.quantity, unit, round=False) for m in finished)
        if produced <= 0:
            raise UserError(_("El lote no tiene producción útil registrada en unidades."))
        layers = native.move_raw_ids.filtered(lambda m: m.state == "done").stock_valuation_layer_ids
        material_cost = -sum(layers.mapped("value"))
        work_cost = sum(order._cal_cost() for order in native.workorder_ids)
        overhead_rows = self.env["step.nursery.batch.allocation.line"].search([
            ("production_id", "=", native.id), ("allocation_id.run_id.state", "=", "done"),
        ])
        overhead_cost = sum(overhead_rows.mapped("amount"))
        scrap = self.env["stock.scrap"].search([
            ("company_id", "=", native.company_id.id), ("state", "=", "done"),
            ("product_id", "=", native.product_id.id), ("lot_id", "=", native.lot_producing_id.id),
        ])
        if any(not loss.step_nursery_waste_kind for loss in scrap):
            raise UserError(_("Clasifique las mermas registradas del lote como normales o anormales."))
        normal, abnormal = [sum(loss.product_uom_id._compute_quantity(loss.scrap_qty, unit, round=False)
                                for loss in scrap if loss.step_nursery_waste_kind == kind)
                            for kind in ("normal", "abnormal")]
        useful = produced - normal - abnormal
        if useful <= 0:
            raise UserError(_("El lote no tiene unidades útiles. Registre la pérdida por separado con Contabilidad."))
        delivered = self.env["stock.move.line"].search([
            ("company_id", "=", native.company_id.id), ("state", "=", "done"),
            ("lot_id", "=", native.lot_producing_id.id), ("product_id", "=", native.product_id.id),
            "|", ("location_id.usage", "=", "customer"), ("location_dest_id.usage", "=", "customer"),
        ])
        sold = sum(
            (1 if line.location_dest_id.usage == "customer" else -1)
            * line.product_uom_id._compute_quantity(line.quantity, unit, round=False)
            for line in delivered
            if line.move_id.sale_line_id or line.move_id.origin_returned_move_id.sale_line_id
        )
        if sold < 0 or sold > useful:
            raise UserError(_("Las entregas netas no concuerdan con las unidades útiles del lote."))
        total = currency.round(material_cost + work_cost + overhead_cost)
        abnormal_cost = currency.round(total * abnormal / produced)
        useful_total = total - abnormal_cost
        unit_cost = useful_total / useful
        sales_cost = currency.round(sold * unit_cost)
        return {
            "production_id": native.id, "material_cost": material_cost, "work_cost": work_cost,
            "overhead_cost": overhead_cost, "normal_waste": normal, "abnormal_waste": abnormal,
            "abnormal_cost": abnormal_cost, "produced": produced, "useful": useful, "sold": sold,
            "unit_cost": unit_cost, "tray_cost": unit_cost * native.step_nursery_plan_ids[:1].cycle_id.cells_per_tray,
            "sales_cost": sales_cost, "balance_cost": useful_total - sales_cost,
            "allocation_ids": [Command.set(overhead_rows.ids)],
        }


class NurseryBatchCostReport(models.TransientModel):
    _name = "step.nursery.batch.cost.report"
    _description = "Costo real y merma de un lote de vivero"

    production_id = fields.Many2one("mrp.production", string="Orden de siembra", required=True, readonly=True)
    currency_id = fields.Many2one(related="production_id.company_id.currency_id")
    material_cost = fields.Monetary(string="Materiales valorizados", readonly=True)
    work_cost = fields.Monetary(string="Costo real de operaciones", readonly=True)
    overhead_cost = fields.Monetary(string="Gastos compartidos asignados", readonly=True)
    produced = fields.Float(string="Producidas", readonly=True)
    normal_waste = fields.Float(string="Merma normal (unidades)", readonly=True)
    abnormal_waste = fields.Float(string="Merma anormal (unidades)", readonly=True)
    abnormal_cost = fields.Monetary(string="Costo separado de merma anormal", readonly=True)
    useful = fields.Float(string="Unidades útiles", readonly=True)
    sold = fields.Float(string="Unidades vendidas netas", readonly=True)
    unit_cost = fields.Float(string="Costo por planta útil", digits=(16, 6), readonly=True)
    tray_cost = fields.Float(string="Costo por bandeja completa", digits=(16, 4), readonly=True)
    sales_cost = fields.Monetary(string="Costo de entregas netas", readonly=True)
    balance_cost = fields.Monetary(string="Costo de saldo útil", readonly=True)
    allocation_ids = fields.Many2many("step.nursery.batch.allocation.line", string="Repartos de respaldo", readonly=True)
