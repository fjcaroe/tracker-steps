from odoo import api, fields, models


class BpaIrrigation(models.Model):
    _name = "x_riego_y_fertilizacio"
    _description = "Riego y fertilización"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "x_studio_fecha_aplicacin desc, id desc"

    x_name = fields.Char(string="Referencia", required=True, default="Nueva orden", tracking=True)
    x_studio_ot_bpa = fields.Char(string="Orden de trabajo")
    x_studio_fecha = fields.Date(string="Fecha", default=fields.Date.context_today)
    x_studio_fecha_aplicacin = fields.Date(string="Fecha de aplicación", default=fields.Date.context_today, tracking=True)
    x_studio_fundo = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    x_studio_responsaable = fields.Many2one("hr.employee", string="Responsable", tracking=True)
    x_studio_tipo_de_aplicacin = fields.Many2one(
        "x_tipo_de_aplicaciones", string="Tipo de aplicación", tracking=True
    )
    x_studio_slo_riego = fields.Boolean(string="Sólo riego", default=True)
    x_studio_hectreas_a_regar = fields.Float(string="Hectáreas a regar")
    x_studio_litros_mezcla = fields.Float(string="Litros de mezcla")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    notes = fields.Html(string="Observaciones")


class BpaFoliarApplication(models.Model):
    _name = "x_aplicacion_foliar"
    _description = "Aplicación foliar BPA"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "x_studio_fecha_hora_planificada desc, id desc"

    x_name = fields.Char(string="Referencia", required=True, default="Nueva aplicación", tracking=True)
    x_studio_nmero_ot_bpa = fields.Char(string="Número OT BPA")
    x_studio_fecha = fields.Date(string="Fecha", default=fields.Date.context_today)
    x_studio_fecha_hora_planificada = fields.Datetime(string="Fecha planificada", default=fields.Datetime.now, tracking=True)
    x_studio_fundo = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    x_studio_especie_1 = fields.Many2one("step.especie", string="Especie")
    x_studio_objetivo_aplicacin = fields.Many2one("x_objetivo_o_plaga", string="Objetivo de aplicación")
    x_studio_aprueba = fields.Many2one("hr.employee", string="Aprueba", tracking=True)
    x_studio_total_hectreas = fields.Float(string="Total hectáreas")
    x_studio_costo_total_aplicacin = fields.Monetary(string="Costo total", compute="_compute_total_cost", store=True)
    x_studio_costo_de_productos = fields.Monetary(string="Costo productos")
    x_studio_costo_de_personal = fields.Monetary(string="Costo personal")
    x_studio_costo_maquinarias = fields.Monetary(string="Costo maquinarias")
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    notes = fields.Html(string="Observaciones")

    @api.depends(
        "x_studio_costo_de_productos",
        "x_studio_costo_de_personal",
        "x_studio_costo_maquinarias",
    )
    def _compute_total_cost(self):
        for record in self:
            record.x_studio_costo_total_aplicacin = (
                record.x_studio_costo_de_productos
                + record.x_studio_costo_de_personal
                + record.x_studio_costo_maquinarias
            )


class BpaAgriculturalMonitoring(models.Model):
    _name = "x_monitoreo_agricola"
    _description = "Monitoreo agrícola"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "x_studio_fecha desc, id desc"

    x_name = fields.Char(string="Referencia", required=True, default="Nuevo monitoreo", tracking=True)
    x_studio_nmero_ot = fields.Char(string="Número OT")
    x_studio_fecha = fields.Date(string="Fecha", default=fields.Date.context_today, tracking=True)
    x_studio_fundo = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    x_studio_especie = fields.Many2one("step.especie", string="Especie")
    x_studio_estado_fenolgico = fields.Many2one("x_estado_fenologico", string="Estado fenológico")
    x_studio_responsable = fields.Many2one("hr.employee", string="Responsable", tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    notes = fields.Html(string="Hallazgos y observaciones")


class BpaIrrigationSector(models.Model):
    _name = "x_sector_de_riego"
    _description = "Sector de riego"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "x_name"

    x_name = fields.Char(string="Sector", required=True, tracking=True)
    x_studio_fundo = fields.Many2one("step.fundo", string="Fundo", tracking=True)
    x_studio_total_hs = fields.Float(string="Total hectáreas")
    irrigation_system = fields.Selection(
        [("drip", "Goteo"), ("sprinkler", "Aspersión"), ("furrow", "Surco"), ("other", "Otro")],
        string="Sistema de riego",
    )
    water_source = fields.Char(string="Fuente de agua")
    soil_type = fields.Char(string="Tipo de suelo")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)


class BpaApplicationType(models.Model):
    _name = "x_tipo_de_aplicaciones"
    _description = "Tipo de aplicación agrícola"
    _order = "x_name"

    x_name = fields.Char(string="Tipo de aplicación", required=True)
    active = fields.Boolean(default=True)


class BpaObjective(models.Model):
    _name = "x_objetivo_o_plaga"
    _description = "Objetivo o plaga"
    _order = "x_name"

    x_name = fields.Char(string="Objetivo o plaga", required=True)
    active = fields.Boolean(default=True)


class BpaPhenologicalState(models.Model):
    _name = "x_estado_fenologico"
    _description = "Estado fenológico"
    _order = "x_name"

    x_name = fields.Char(string="Estado fenológico", required=True)
    active = fields.Boolean(default=True)
