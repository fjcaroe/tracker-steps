from odoo import api, fields, models


class BpaIrrigation(models.Model):
    _name = "step.agriculture.irrigation"
    _description = "Riego y fertilización"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "fecha_aplicacin desc, id desc"

    name = fields.Char(string="Referencia", required=True, default="Nueva orden", tracking=True)
    ot_bpa = fields.Char(string="Orden de trabajo")
    date = fields.Date(string="Fecha", default=fields.Date.context_today)
    fecha_aplicacin = fields.Date(string="Fecha de aplicación", default=fields.Date.context_today, tracking=True)
    fundo_id = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    responsaable_id = fields.Many2one("hr.employee", string="Responsable", tracking=True)
    tipo_de_aplicacin_id = fields.Many2one(
        "step.agriculture.application.type", string="Tipo de aplicación", tracking=True
    )
    slo_riego = fields.Boolean(string="Sólo riego", default=True)
    hectreas_a_regar = fields.Float(string="Hectáreas a regar")
    litros_mezcla = fields.Float(string="Litros de mezcla")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    notes = fields.Html(string="Observaciones")


class BpaFoliarApplication(models.Model):
    _name = "step.agriculture.application"
    _description = "Aplicación foliar BPA"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "fecha_hora_planificada desc, id desc"

    name = fields.Char(string="Referencia", required=True, default="Nueva aplicación", tracking=True)
    state = fields.Selection(
        [("status1", "Ingresado"), ("status2", "Aprobado"),
         ("status3", "Costeado"), ("Contabilizado", "Contabilizado")],
        string="Estado", default="status1", required=True, tracking=True, index=True,
    )
    nmero_ot_bpa = fields.Char(string="Número OT BPA")
    date = fields.Date(string="Fecha", default=fields.Date.context_today)
    fecha_hora_planificada = fields.Datetime(string="Fecha planificada", default=fields.Datetime.now, tracking=True)
    fundo_id = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    especie_1_id = fields.Many2one("step.especie", string="Especie")
    objetivo_aplicacin_id = fields.Many2one("step.agriculture.pest", string="Objetivo de aplicación")
    aprueba_id = fields.Many2one("hr.employee", string="Aprueba", tracking=True)
    total_hectreas = fields.Float(string="Total hectáreas")
    costo_total_aplicacin = fields.Monetary(string="Costo total", compute="_compute_total_cost", store=True)
    costo_de_productos = fields.Monetary(string="Costo productos")
    costo_de_personal = fields.Monetary(string="Costo personal")
    costo_maquinarias = fields.Monetary(string="Costo maquinarias")
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    notes = fields.Html(string="Observaciones")

    @api.depends(
        "costo_de_productos",
        "costo_de_personal",
        "costo_maquinarias",
    )
    def _compute_total_cost(self):
        for record in self:
            record.costo_total_aplicacin = (
                record.costo_de_productos
                + record.costo_de_personal
                + record.costo_maquinarias
            )


class BpaAgriculturalMonitoring(models.Model):
    _name = "step.agriculture.monitoring"
    _description = "Monitoreo agrícola"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(string="Referencia", required=True, default="Nuevo monitoreo", tracking=True)
    nmero_ot = fields.Char(string="Número OT")
    date = fields.Date(string="Fecha", default=fields.Date.context_today, tracking=True)
    fundo_id = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    species_id = fields.Many2one("step.especie", string="Especie")
    estado_fenolgico_id = fields.Many2one("step.agriculture.phenological.stage", string="Estado fenológico")
    responsable_id = fields.Many2one("hr.employee", string="Responsable", tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    notes = fields.Html(string="Hallazgos y observaciones")


class BpaIrrigationSector(models.Model):
    _name = "step.agriculture.irrigation.sector"
    _description = "Sector de riego"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Sector", required=True, tracking=True)
    fundo_id = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    total_hs = fields.Float(string="Total hectáreas")
    irrigation_system = fields.Selection(
        [("drip", "Goteo"), ("sprinkler", "Aspersión"), ("furrow", "Surco"), ("other", "Otro")],
        string="Sistema de riego",
    )
    water_source = fields.Char(string="Fuente de agua")
    soil_type = fields.Char(string="Tipo de suelo")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)


class BpaApplicationType(models.Model):
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _name = "step.agriculture.application.type"
    _description = "Tipo de aplicación agrícola"
    _order = "name"

    name = fields.Char(string="Tipo de aplicación", required=True)
    active = fields.Boolean(default=True)


class BpaObjective(models.Model):
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _name = "step.agriculture.pest"
    _description = "Objetivo o plaga"
    _order = "name"

    name = fields.Char(string="Objetivo o plaga", required=True)
    active = fields.Boolean(default=True)


class BpaPhenologicalState(models.Model):
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _name = "step.agriculture.phenological.stage"
    _description = "Estado fenológico"
    _order = "name"

    name = fields.Char(string="Estado fenológico", required=True)
    active = fields.Boolean(default=True)
