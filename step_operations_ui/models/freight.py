from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FreightRoute(models.Model):
    _name = "x_tramo_de_flete"
    _description = "Tramo de flete"
    _order = "x_name"

    x_name = fields.Char(string="Tramo", required=True)
    origin = fields.Char(string="Origen", required=True)
    destination = fields.Char(string="Destino", required=True)
    distance_km = fields.Float(string="Distancia (km)")
    x_active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)


class FreightColdMode(models.Model):
    _name = "x_modalidad_de_frio"
    _description = "Modalidad de frío"
    _order = "x_name"

    x_name = fields.Char(string="Modalidad", required=True)
    min_temperature = fields.Float(string="Temperatura mínima")
    max_temperature = fields.Float(string="Temperatura máxima")
    x_active = fields.Boolean(string="Activa", default=True)


class FreightTariff(models.Model):
    _name = "x_tarifa_de_fletes"
    _description = "Tarifa de flete"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "valid_from desc, id desc"

    x_name = fields.Char(string="Tarifa", required=True, tracking=True)
    carrier_id = fields.Many2one("res.partner", string="Transportista", domain="[('supplier_rank', '>', 0)]", tracking=True)
    route_id = fields.Many2one("x_tramo_de_flete", string="Tramo", required=True)
    cold_mode_id = fields.Many2one("x_modalidad_de_frio", string="Modalidad de frío")
    price = fields.Monetary(string="Valor", required=True, tracking=True)
    valid_from = fields.Date(string="Vigente desde", default=fields.Date.context_today)
    valid_to = fields.Date(string="Vigente hasta")
    x_active = fields.Boolean(string="Activa", default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)


class FreightOrder(models.Model):
    _name = "x_orden_de_flete"
    _description = "Orden de flete"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "x_studio_fecha desc, id desc"

    x_name = fields.Char(string="Orden", required=True, default="Nueva orden", tracking=True)
    x_studio_fecha = fields.Date(string="Fecha", default=fields.Date.context_today, tracking=True)
    x_studio_selection_field_4ag_1jhk4c7s5 = fields.Selection(
        [("status1", "Ingresado"), ("status2", "Autorizado"), ("status3", "Contabilizado"), ("cancel", "Anulado")],
        string="Estado",
        default="status1",
        tracking=True,
    )
    x_studio_fundo = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    x_studio_transportista = fields.Many2one("res.partner", string="Transportista", domain="[('supplier_rank', '>', 0)]", tracking=True)
    x_studio_responsable = fields.Many2one("hr.employee", string="Responsable", tracking=True)
    route_id = fields.Many2one("x_tramo_de_flete", string="Tramo")
    tariff_id = fields.Many2one("x_tarifa_de_fletes", string="Tarifa")
    cold_mode_id = fields.Many2one("x_modalidad_de_frio", string="Modalidad de frío")
    vehicle_id = fields.Many2one("fleet.vehicle", string="Camión")
    quantity = fields.Float(string="Cantidad")
    amount = fields.Monetary(string="Valor", compute="_compute_amount", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    notes = fields.Html(string="Observaciones")

    @api.depends("tariff_id.price", "quantity")
    def _compute_amount(self):
        for record in self:
            record.amount = record.tariff_id.price * (record.quantity or 1.0)


class FreightAccounting(models.Model):
    _name = "x_contabilizacion_de_f"
    _description = "Contabilización de flete"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "accounting_date desc, id desc"

    x_name = fields.Char(string="Referencia", required=True, default="Nueva contabilización")
    order_id = fields.Many2one("x_orden_de_flete", string="Orden de flete", required=True, ondelete="restrict")
    accounting_date = fields.Date(string="Fecha contable", default=fields.Date.context_today)
    move_id = fields.Many2one("account.move", string="Asiento contable", readonly=True)
    amount = fields.Monetary(related="order_id.amount", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id", store=True)
    company_id = fields.Many2one(related="order_id.company_id", store=True)


class FreightTracking(models.Model):
    _name = "x_rastreo_camiones"
    _description = "Rastreo de camiones"
    _order = "event_datetime desc, id desc"

    x_name = fields.Char(string="Evento", required=True, default="Nueva posición")
    order_id = fields.Many2one("x_orden_de_flete", string="Orden de flete", required=True, ondelete="cascade")
    event_datetime = fields.Datetime(string="Fecha y hora", default=fields.Datetime.now, required=True)
    latitude = fields.Float(string="Latitud", digits=(10, 7))
    longitude = fields.Float(string="Longitud", digits=(10, 7))
    note = fields.Char(string="Observación")


class FreightDispatchType(models.Model):
    _name = "x_tipo_despacho"
    _description = "Tipo de despacho"
    _order = "x_name"

    x_name = fields.Char(string="Tipo de despacho", required=True)
    paga_flete = fields.Selection(
        [("no", "No"), ("opcional", "Opcional"), ("si", "Sí")],
        string="¿Paga flete?",
        default="no",
        required=True,
    )
    x_active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)


class FreightPlan(models.Model):
    _name = "x_planificacion_de_flete"
    _description = "Planificación de flete"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "x_studio_fecha desc, id desc"

    x_name = fields.Char(string="Planificación", required=True, default="Nueva planificación", tracking=True)
    x_studio_fecha = fields.Date(string="Fecha", default=fields.Date.context_today, tracking=True)
    x_studio_fundo = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    x_studio_responsable = fields.Many2one("hr.employee", string="Responsable", tracking=True)
    line_ids = fields.One2many("x_planificacion_de_flete_linea", "plan_id", string="Líneas de flete")
    amount_total = fields.Monetary(string="Total flete", compute="_compute_amount_total", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    @api.depends("line_ids.amount_total")
    def _compute_amount_total(self):
        for plan in self:
            plan.amount_total = sum(plan.line_ids.mapped("amount_total"))


class FreightPlanLine(models.Model):
    _name = "x_planificacion_de_flete_linea"
    _description = "Línea de planificación de flete"
    _order = "id"

    plan_id = fields.Many2one("x_planificacion_de_flete", string="Planificación", required=True, ondelete="cascade")
    description = fields.Char(string="Descripción")
    product_id = fields.Many2one(
        "product.template", string="Producto", required=True, domain="[('is_flete', '=', True)]"
    )
    uom_id = fields.Many2one(related="product_id.uom_id", string="Unidad de flete", store=True)
    quantity = fields.Float(string="Cantidad", default=1.0)
    price = fields.Monetary(string="Precio")
    amount_total = fields.Monetary(string="Total flete", compute="_compute_amount_total", store=True)
    currency_id = fields.Many2one(related="plan_id.currency_id", store=True)

    @api.depends("quantity", "price")
    def _compute_amount_total(self):
        for line in self:
            line.amount_total = (line.quantity or 0.0) * (line.price or 0.0)

    @api.constrains("product_id")
    def _check_product_is_flete(self):
        for line in self:
            if line.product_id and not line.product_id.is_flete:
                raise ValidationError(
                    "El producto de la línea de flete debe estar marcado como "
                    "'Es flete?' en el maestro de productos."
                )
