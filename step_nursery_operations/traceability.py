from math import floor, isfinite

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockLot(models.Model):
    _inherit = "stock.lot"

    step_nursery_seed = fields.Boolean(string="Semilla de vivero")
    step_nursery_variety_id = fields.Many2one("step.variedad", string="Variedad de semilla",
                                              check_company=True, ondelete="restrict")
    step_nursery_sample = fields.Integer(string="Semillas en muestra")
    step_nursery_germinated = fields.Integer(string="Semillas germinadas")
    step_nursery_germination_pct = fields.Float(string="Germinación (%)", compute="_compute_nursery_seed", store=True)
    step_nursery_weight_g = fields.Float(string="Peso neto de muestra (g)", digits=(16, 4))
    step_nursery_seeds_per_g = fields.Float(string="Semillas por gramo", compute="_compute_nursery_seed",
                                           store=True, digits=(16, 4))

    @api.depends("step_nursery_sample", "step_nursery_germinated", "step_nursery_weight_g")
    def _compute_nursery_seed(self):
        for lot in self:
            lot.step_nursery_germination_pct = (
                100 * lot.step_nursery_germinated / lot.step_nursery_sample if lot.step_nursery_sample else 0)
            lot.step_nursery_seeds_per_g = (
                lot.step_nursery_sample / lot.step_nursery_weight_g if lot.step_nursery_weight_g else 0)

    @api.constrains("step_nursery_sample", "step_nursery_germinated", "step_nursery_weight_g")
    def _check_nursery_sample(self):
        for lot in self:
            if (not 0 <= lot.step_nursery_germinated <= lot.step_nursery_sample
                    or not isfinite(lot.step_nursery_weight_g) or lot.step_nursery_weight_g < 0
                    or (lot.step_nursery_weight_g and not lot.step_nursery_sample)):
                raise ValidationError(_("Revise el tamaño, peso y conteo germinado de la muestra."))


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    step_nursery_plan_ids = fields.One2many("step.nursery.plan", "production_id", string="Planes de siembra")
    step_nursery_event_ids = fields.One2many("step.nursery.event", "production_id", string="Bitácora de vivero")
    step_nursery_input_lot_ids = fields.Many2many("stock.lot", string="Lotes de insumos consumidos",
                                                  compute="_compute_nursery_input_lots")

    @api.depends("move_raw_ids.state", "move_raw_ids.move_line_ids.lot_id", "move_raw_ids.move_line_ids.quantity")
    def _compute_nursery_input_lots(self):
        for production in self:
            production.step_nursery_input_lot_ids = production.move_raw_ids.filtered(
                lambda move: move.state == "done").move_line_ids.filtered(lambda line: line.quantity > 0).lot_id


class NurseryEvent(models.Model):
    _name = "step.nursery.event"
    _description = "Labor o medición de un lote de vivero"
    _order = "performed_at desc, id desc"
    _check_company_auto = True

    production_id = fields.Many2one("mrp.production", string="Orden de siembra", required=True,
                                     check_company=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="production_id.company_id", store=True, index=True)
    finished_lot_id = fields.Many2one(related="production_id.lot_producing_id", string="Lote de plantines")
    performed_at = fields.Datetime(string="Realizado el", required=True, default=fields.Datetime.now)
    operator_id = fields.Many2one("res.users", string="Responsable", required=True,
                                   default=lambda self: self.env.user)
    kind = fields.Selection([
        ("germination", "Germinación"), ("watering", "Riego"), ("fertilizing", "Fertilización"),
        ("treatment", "Aplicación fitosanitaria"), ("observation", "Observación"),
    ], required=True)
    workorder_id = fields.Many2one("mrp.workorder", string="Operación", ondelete="restrict")
    material_id = fields.Many2one("product.product", string="Insumo aplicado", check_company=True)
    quantity = fields.Float(string="Dosis", digits="Product Unit of Measure")
    uom_id = fields.Many2one("uom.uom", string="Unidad de dosis")
    sample_count = fields.Integer(string="Muestra")
    germinated_count = fields.Integer(string="Germinadas")
    germination_pct = fields.Float(string="Germinación (%)", compute="_compute_germination", store=True)
    note = fields.Text(string="Observación")

    @api.depends("sample_count", "germinated_count")
    def _compute_germination(self):
        for event in self:
            event.germination_pct = 100 * event.germinated_count / event.sample_count if event.sample_count else 0

    @api.constrains("production_id", "workorder_id", "kind", "material_id", "quantity",
                    "uom_id", "sample_count", "germinated_count", "operator_id")
    def _check_event(self):
        for event in self:
            if event.workorder_id and event.workorder_id.production_id != event.production_id:
                raise ValidationError(_("La operación debe pertenecer a la orden de siembra."))
            if event.company_id not in event.operator_id.company_ids:
                raise ValidationError(_("El responsable debe pertenecer a la empresa de la siembra."))
            if event.kind == "germination" and not (0 <= event.germinated_count <= event.sample_count
                                                     and event.sample_count > 0):
                raise ValidationError(_("Ingrese una muestra positiva y su conteo germinado."))
            if event.kind in ("fertilizing", "treatment") and (
                    not event.material_id or not event.uom_id or not isfinite(event.quantity)
                    or event.quantity <= 0 or event.uom_id.category_id != event.material_id.uom_id.category_id):
                raise ValidationError(_("Indique insumo, dosis positiva y unidad compatible."))



class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    step_nursery_net_seed_g = fields.Float(string="Peso neto de semilla (g)", digits=(16, 4), copy=False)
    step_nursery_seed_rate_used = fields.Float(string="Semillas por gramo aplicadas", digits=(16, 4),
                                               readonly=True, copy=False)
    step_nursery_can_convert_seed = fields.Boolean(compute="_compute_can_convert_seed")

    @api.depends("lot_id.step_nursery_seed", "picking_id.picking_type_id.code", "state")
    def _compute_can_convert_seed(self):
        for line in self:
            line.step_nursery_can_convert_seed = (
                line.lot_id.step_nursery_seed and line.picking_id.picking_type_id.code == "incoming"
                and line.state not in ("done", "cancel"))

    @api.constrains("step_nursery_net_seed_g")
    def _check_seed_weight(self):
        if any(not isfinite(line.step_nursery_net_seed_g) or line.step_nursery_net_seed_g < 0 for line in self):
            raise ValidationError(_("El peso neto de semilla debe ser un número no negativo."))

    def action_step_nursery_apply_seed_weight(self):
        self.ensure_one()
        self.check_access("write")
        if not self.step_nursery_can_convert_seed or self.step_nursery_net_seed_g <= 0:
            raise ValidationError(_("Indique el peso y un lote de semilla en una recepción pendiente."))
        uom = self.product_uom_id
        gram = self.env.ref("uom.product_uom_gram")
        unit = self.env.ref("uom.product_uom_unit")
        rate = 0
        if uom.category_id == unit.category_id:
            lot = self.lot_id
            if not lot.step_nursery_weight_g or not lot.step_nursery_sample:
                raise ValidationError(_("Registre una muestra pesada en este lote antes de estimar unidades."))
            rate = lot.step_nursery_sample / lot.step_nursery_weight_g
            whole_seeds = floor(round(self.step_nursery_net_seed_g * rate, 8))
            qty = unit._compute_quantity(whole_seeds, uom, rounding_method="DOWN")
        elif uom.category_id == gram.category_id:
            qty = gram._compute_quantity(self.step_nursery_net_seed_g, uom, rounding_method="HALF-UP")
        else:
            raise ValidationError(_("La unidad de la recepción debe ser de peso o de unidades."))
        if qty <= 0:
            raise ValidationError(_("El peso no alcanza la mínima cantidad de la unidad de inventario."))
        self.write({"quantity": qty, "step_nursery_seed_rate_used": rate})
        return True
