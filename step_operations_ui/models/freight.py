from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FreightRoute(models.Model):
    _name = "step.freight.route"
    _description = "Tramo de flete"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "name"

    name = fields.Char(string="Tramo", required=True)
    origin = fields.Char(string="Origen", required=True)
    destination = fields.Char(string="Destino", required=True)
    distance_km = fields.Float(string="Distancia (km)")
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)


class FreightColdMode(models.Model):
    _name = "step.freight.cold.mode"
    _description = "Modalidad de frío"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "name"

    name = fields.Char(string="Modalidad", required=True)
    min_temperature = fields.Float(string="Temperatura mínima")
    max_temperature = fields.Float(string="Temperatura máxima")
    active = fields.Boolean(string="Activa", default=True)
    # Keep the original columns and IDs; these fields are now owned by Python.
    code = fields.Char(string="Código")
    sequence = fields.Integer(string="Secuencia")


class FreightTariff(models.Model):
    _name = "step.freight.tariff"
    _description = "Tarifa de flete"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "valid_from desc, id desc"

    name = fields.Char(string="Tarifa", required=True, tracking=True)
    carrier_id = fields.Many2one("res.partner", string="Transportista", domain="[('is_freight_carrier', '=', True)]", tracking=True)
    # route_id/price ya no son obligatorios a nivel de encabezado: desde la
    # migración del formulario de Studio (ticket T27, puntos 3 y 4) el tramo y
    # la tarifa se registran por línea (ver step.freight.tariff.line en
    # freight_studio.py). El formulario code-owned (prioridad 5) no expone
    # estos dos campos de encabezado, así que si siguieran siendo required=True
    # sería imposible guardar una tarifa nueva desde esa pantalla.
    route_id = fields.Many2one("step.freight.route", string="Tramo")
    cold_mode_id = fields.Many2one("step.freight.cold.mode", string="Modalidad de frío")
    price = fields.Monetary(string="Valor", tracking=True)
    valid_from = fields.Date(string="Vigente desde", default=fields.Date.context_today)
    valid_to = fields.Date(string="Vigente hasta")
    active = fields.Boolean(string="Activa", default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)


class FreightOrder(models.Model):
    _name = "step.freight.order"
    _description = "Orden de flete"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(string="Orden", required=True, default="Nueva orden", tracking=True)
    date = fields.Date(string="Fecha", default=fields.Date.context_today, tracking=True)
    freight_state = fields.Selection(
        [("status1", "Ingresado"), ("status2", "Autorizado"), ("status3", "Contabilizado"), ("cancel", "Anulado")],
        string="Estado",
        default="status1",
        tracking=True,
    )
    fundo_id = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    freight_carrier_id = fields.Many2one("res.partner", string="Transportista", domain="[('is_freight_carrier', '=', True)]", tracking=True)
    responsible_id = fields.Many2one("hr.employee", string="Responsable", tracking=True)
    route_id = fields.Many2one("step.freight.route", string="Tramo")
    tariff_id = fields.Many2one("step.freight.tariff", string="Tarifa")
    cold_mode_id = fields.Many2one("step.freight.cold.mode", string="Modalidad de frío")
    vehicle_id = fields.Many2one(
        "fleet.vehicle", string="Camión", domain="[('category_id.name', 'ilike', 'carga')]"
    )
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
    _name = "step.freight.accounting"
    _description = "Contabilización de flete"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "accounting_date desc, id desc"

    name = fields.Char(string="Referencia", required=True, default="Nueva contabilización")
    order_id = fields.Many2one("step.freight.order", string="Orden de flete", required=True, ondelete="restrict")
    accounting_date = fields.Date(string="Fecha contable", default=fields.Date.context_today)
    move_id = fields.Many2one("account.move", string="Asiento contable", readonly=True)
    amount = fields.Monetary(related="order_id.amount", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id", store=True)
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer()


class FreightTracking(models.Model):
    _name = "step.freight.tracking"
    _description = "Rastreo de camiones"
    _order = "event_datetime desc, id desc"

    name = fields.Char(string="Evento", required=True, default="Nueva posición")
    order_id = fields.Many2one("step.freight.order", string="Orden de flete", required=True, ondelete="cascade")
    event_datetime = fields.Datetime(string="Fecha y hora", default=fields.Datetime.now, required=True)
    latitude = fields.Float(string="Latitud", digits=(10, 7))
    longitude = fields.Float(string="Longitud", digits=(10, 7))
    note = fields.Char(string="Observación")
    active = fields.Boolean(default=True)
    sequence = fields.Integer()


class FreightDispatchType(models.Model):
    _name = "step.freight.dispatch.type"
    _description = "Tipo de despacho"
    _order = "name"

    name = fields.Char(string="Tipo de despacho", required=True)
    paga_flete = fields.Selection(
        [("no", "No"), ("opcional", "Opcional"), ("si", "Sí")],
        string="¿Paga flete?",
        default="no",
        required=True,
    )
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)


class FreightPlan(models.Model):
    _name = "step.freight.plan"
    _description = "Planificación de flete"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(string="Planificación", required=True, default="Nueva planificación", tracking=True)
    date = fields.Date(string="Fecha", default=fields.Date.context_today, tracking=True)
    date_from = fields.Date(string="Fecha desde", tracking=True)
    date_to = fields.Date(string="Fecha hasta", tracking=True)
    fundo_id = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    responsible_id = fields.Many2one("hr.employee", string="Responsable", tracking=True)
    state = fields.Selection(
        [("draft", "Creado"), ("validated", "Validado")],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many("step.freight.plan.line", "plan_id", string="Líneas de flete")
    amount_total = fields.Monetary(string="Total flete", compute="_compute_amount_total", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for plan in self:
            if plan.date_from and plan.date_to and plan.date_from > plan.date_to:
                raise ValidationError("La fecha desde no puede ser posterior a la fecha hasta.")

    @api.depends("line_ids.amount_total", "line_ids.currency_id", "company_id", "date")
    def _compute_amount_total(self):
        for plan in self:
            conversion_date = plan.date or fields.Date.context_today(plan)
            total = 0.0
            for line in plan.line_ids:
                if line.currency_id and line.currency_id != plan.currency_id:
                    total += line.currency_id._convert(
                        line.amount_total, plan.currency_id, plan.company_id, conversion_date
                    )
                else:
                    total += line.amount_total
            plan.amount_total = total

    def action_validate(self):
        for plan in self:
            if not plan.line_ids:
                raise ValidationError("No se puede validar una planificación sin líneas de flete.")
            plan.state = "validated"

    def action_reset_to_draft(self):
        self.state = "draft"


class FreightPlanLine(models.Model):
    _name = "step.freight.plan.line"
    _description = "Línea de planificación de flete"
    _order = "id"

    plan_id = fields.Many2one("step.freight.plan", string="Planificación", required=True, ondelete="cascade")
    description = fields.Char(string="Descripción")
    product_id = fields.Many2one(
        "product.template", string="Producto", required=True, domain="[('is_flete', '=', True)]"
    )
    uom_id = fields.Many2one(related="product_id.uom_id", string="Unidad de flete", store=True)
    quantity = fields.Float(string="Cantidad", default=1.0)
    price = fields.Monetary(string="Precio")
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", default=lambda self: self.env.company.currency_id.id
    )
    amount_total = fields.Monetary(string="Total flete", compute="_compute_amount_total", store=True)

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
