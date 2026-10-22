"""Static agricultural fields, preserving the audited types and relations."""
from odoo import api, fields, models


class StepAgricultureInspection(models.Model):
    _name = 'step.agriculture.inspection'
    _description = 'Inspecciones internas'
    _rec_name = "name"
    _order = "id"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _folio_sequence = 'interna.inspecciones'
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    name = fields.Char(string='Folio inspección interna', required=False, readonly=True, copy=True, store=True, default="Nuevo")
    asignado_a_id = fields.Many2one(string='Asignado a', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    cost_center_id = fields.Many2one(string='Centro costos', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    date = fields.Date(string='Fecha', required=False, readonly=False, copy=True, store=True)
    fecha_a_ejecutar = fields.Date(string='Fecha a ejecutar', required=False, readonly=False, copy=True, store=True)
    fundo_id = fields.Many2one(string='Fundo', required=False, readonly=False, copy=True, store=True, comodel_name='step.fundo', ondelete='set null')
    instructions_html = fields.Html(string='Nuevo HTML', required=False, readonly=False, copy=True, store=True)
    instruccin = fields.Text(string='Instrucción', required=False, readonly=False, copy=True, store=True)
    observaciones = fields.Text(string='Observaciones', required=False, readonly=False, copy=True, store=True)
    line_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.inspection.line', inverse_name='inspection_id')
    responsable_id = fields.Many2one(string='Responsable', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    sector_riego_id = fields.Many2one(string='Sector riego', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation.sector', ondelete='set null')
    state = fields.Selection(string='Barra de estado de flujo', required=False, readonly=False, copy=True, store=True, selection=[['status1', 'Creada'], ['status2', 'Ejecutada'], ['status3', 'Aprobada']], default='status1')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if not values.get("name") or values["name"] == "Nuevo":
                values["name"] = self.env["ir.sequence"].next_by_code(self._folio_sequence) or "/"
        return super().create(values_list)


class StepAgricultureIrrigationSector(models.Model):
    _inherit = 'step.agriculture.irrigation.sector'
    legacy_active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True)
    cdigo_sdp = fields.Char(string='Código SDP', required=False, readonly=False, copy=True, store=True)
    fuente_de_agua = fields.Selection(string='Fuente de agua', required=False, readonly=False, copy=True, store=True, selection=[['Canal', 'Canal'], ['Tranque', 'Tranque'], ['Pozo', 'Pozo'], ['Noria', 'Noria'], ['Vertiente', 'Vertiente']])
    hs_disponibles = fields.Float(string='Hás. disponibles', required=False, readonly=False, copy=True, store=True)
    hs_otros_usos = fields.Float(string='Hás. otros usos', required=False, readonly=False, copy=True, store=True)
    hs_plantadas = fields.Float(string='Hás. plantadas', required=False, readonly=False, copy=True, store=True)
    valve_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.irrigation.valve', inverse_name='sector_id')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    sistema_de_riego = fields.Selection(string='Sistema de riego', required=False, readonly=False, copy=True, store=True, selection=[['Goteo', 'Goteo'], ['Zurco', 'Zurco'], ['Aspersión', 'Aspersión'], ['Mangas', 'Mangas'], ['Otro', 'Otro']])
    tipo_de_suelo = fields.Selection(string='Tipo de suelo', required=False, readonly=False, copy=True, store=True, selection=[['Franco', 'Franco'], ['Arenoso', 'Arenoso'], ['Limoso', 'Limoso'], ['Arcilloso', 'Arcilloso']])
    uso_del_sueldo = fields.Selection(string='Uso del sueldo', required=False, readonly=False, copy=True, store=True, selection=[['Frutales', 'Frutales'], ['Ganadería', 'Ganadería'], ['Forestal', 'Forestal'], ['Cultivo anual', 'Cultivo anual'], ['Otro', 'Otro']])


class StepAgricultureIrrigationValve(models.Model):
    _name = 'step.agriculture.irrigation.valve'
    _description = 'sector_de_riego_line'
    _rec_name = "name"
    _order = "id"
    name = fields.Char(string='Válvula', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    sector_id = fields.Many2one(string='X Sector De Riego', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation.sector', ondelete='set null')
    cc_id = fields.Many2one(string='cc', required=False, readonly=False, copy=True, store=True, comodel_name='step.centro.costo', ondelete='set null')
    cuartel_id = fields.Many2one(string='Cuartel', required=False, readonly=False, copy=True, store=True, comodel_name='step.cuartel.line', ondelete='set null')
    cost_center_id = fields.Many2one(string='Centro costos', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    has_ccosto = fields.Integer(string='Has CCosto', required=False, readonly=True, copy=False, store=False, compute='_compute_has_ccosto')
    has_cuartel = fields.Integer(string='Has cuartel', required=False, readonly=True, copy=False, store=False, compute='_compute_has_cuartel')
    lts_por_minuto = fields.Float(string='Lts por minuto', required=False, readonly=False, copy=True, store=True)
    related_sector_id = fields.Many2one(string='Nuevo Many2One', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation.sector', ondelete='set null')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)

    @api.depends()
    def _compute_has_ccosto(self):
        for record in self:
            record['has_ccosto'] = False

    @api.depends()
    def _compute_has_cuartel(self):
        for record in self:
            record['has_cuartel'] = False


class StepAgricultureInspectionLine(models.Model):
    _name = 'step.agriculture.inspection.line'
    _description = 'inspecciones_interna_line'
    _rec_name = "name"
    _order = "id"
    inspection_id = fields.Many2one(string='X Inspecciones Interna', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.inspection', ondelete='set null')
    name = fields.Char(string='Descripción', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureAdvisory(models.Model):
    _name = 'step.agriculture.advisory'
    _description = 'Asesor externo'
    _rec_name = "name"
    _order = "id"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _folio_sequence = 'asesor.inspecciones'
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    name = fields.Char(string='Folio asesoría', required=False, readonly=True, copy=False, store=True, default="Nuevo")
    actividad_id = fields.Many2one(string='Actividad', required=False, readonly=False, copy=True, store=True, comodel_name='step.actividad', ondelete='set null')
    aprobador_id = fields.Many2one(string='Aprobador', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    cost_center_id = fields.Many2one(string='Centro costo', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    descripcin = fields.Char(string='Descripción asesoría', required=False, readonly=False, copy=True, store=True)
    species_id = fields.Many2one(string='Especie', required=False, readonly=False, copy=True, store=True, comodel_name='step.especie', ondelete='set null')
    date = fields.Date(string='Fecha', required=False, readonly=False, copy=True, store=True)
    fecha_a_ejecutar = fields.Date(string='Fecha a ejecutar', required=False, readonly=False, copy=True, store=True)
    fundo_id = fields.Many2one(string='Fundo', required=False, readonly=False, copy=True, store=True, comodel_name='step.fundo', ondelete='set null')
    instructions_html = fields.Html(string='Nuevo HTML', required=False, readonly=False, copy=True, store=True)
    nombre_asesor_id = fields.Many2one(string='Nombre asesor', required=False, readonly=False, copy=True, store=True, comodel_name='res.partner', ondelete='set null')
    line_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.advisory.line', inverse_name='advisory_id')
    responsable_de_ejecutar_id = fields.Many2one(string='Responsable de ejecutar', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    state = fields.Selection(string='Barra de estado de flujo', required=False, readonly=False, copy=True, store=True, selection=[['status1', 'Creada'], ['status2', 'Ejecutada'], ['status3', 'Aprobada'], ['Revisada asesor', 'Revisada asesor']], default='status1')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if not values.get("name") or values["name"] == "Nuevo":
                values["name"] = self.env["ir.sequence"].next_by_code(self._folio_sequence) or "/"
        return super().create(values_list)


class StepAgricultureAdvisoryLine(models.Model):
    _name = 'step.agriculture.advisory.line'
    _description = 'asesor_externo_line'
    _rec_name = "name"
    _order = "id"
    advisory_id = fields.Many2one(string='X Asesor Externo', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.advisory', ondelete='set null')
    name = fields.Char(string='Resultado esperado', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    dosis_por_ha = fields.Char(string='Dosis por ha', required=False, readonly=False, copy=True, store=True)
    labor_tarea_id = fields.Many2one(string='labor, tarea', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    producto_agrcola_id = fields.Many2one(string='Producto agrícola', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    sustancia_activa_id = fields.Many2one(string='Sustancia activa', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.active.ingredient', ondelete='set null')


class StepAgricultureActiveIngredient(models.Model):
    _name = 'step.agriculture.active.ingredient'
    _description = 'Sustancia activa'
    _rec_name = "name"
    _order = "id"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    name = fields.Char(string='Descripción', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    cdigo = fields.Char(string='Código', required=False, readonly=False, copy=True, store=True)
    observacin = fields.Html(string='Observación', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureMonitoringLine(models.Model):
    _name = 'step.agriculture.monitoring.line'
    _description = 'monitoreo_agricola_line'
    _rec_name = "name"
    _order = "id"
    monitoring_id = fields.Many2one(string='X Monitoreo Agricola', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.monitoring', ondelete='set null')
    name = fields.Char(string='Línea', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    cost_center_id = fields.Many2one(string='Centro costos', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    comentario = fields.Char(string='Comentario', required=False, readonly=False, copy=True, store=True)
    cuartel_id = fields.Many2one(string='Cuartel', required=False, readonly=False, copy=True, store=True, comodel_name='step.cuartel.line', ondelete='set null')
    hallazgo = fields.Selection(string='Hallazgo', required=False, readonly=False, copy=True, store=True, selection=[['Presencia', 'Presencia'], ['Ausencia', 'Ausencia']])
    has_cuartel = fields.Integer(string='Has cuartel', required=False, readonly=True, copy=False, store=False, compute='_compute_has_cuartel')
    hileras = fields.Integer(string='Hileras', required=False, readonly=True, copy=False, store=False, related='cuartel_id.hilera_cuartel')
    objetivo_plaga_id = fields.Many2one(string='Objetivo plaga', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.pest', ondelete='set null')
    plantas_cuartel = fields.Integer(string='Plantas cuartel', required=False, readonly=True, copy=False, store=False, related='cuartel_id.plant_cuartel')
    plantas_muesteadas = fields.Float(string='Plantas muesteadas', required=False, readonly=False, copy=True, store=True)
    available_cuartel_ids = fields.One2many(string='Nuevo Campo relacionado', required=False, readonly=True, copy=False, store=False, comodel_name='step.cuartel.line', related='cost_center_id.cuartel_line')
    seales_de_plaga = fields.Selection(string='Señales de plaga', required=False, readonly=False, copy=True, store=True, selection=[['Animal vivo', 'Animal vivo'], ['Animal muerto', 'Animal muerto'], ['Daños', 'Daños'], ['Excremento', 'Excremento']])
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)

    @api.depends()
    def _compute_has_cuartel(self):
        for record in self:
            record['has_cuartel'] = False


class StepAgriculturePest(models.Model):
    _inherit = 'step.agriculture.pest'
    legacy_active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True)
    cdigo_de_objetivo = fields.Char(string='Código de objetivo', required=False, readonly=False, copy=True, store=True)
    grupo_objetivo_bpa = fields.Selection(string='Grupo objetivo BPA', required=False, readonly=False, copy=True, store=True, selection=[['Plagas', 'Plagas'], ['Malezas', 'Malezas'], ['Nutrición', 'Nutrición']])
    observacin = fields.Html(string='Observación', required=False, readonly=False, copy=True, store=True)
    rango_fecha = fields.Date(string='Rango fecha', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureMonitoring(models.Model):
    _inherit = 'step.agriculture.monitoring'
    _folio_sequence = 'monitoreo.bpa'
    name = fields.Char(default="Nuevo")
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    ejecutado_por_id = fields.Many2one(string='Ejecutado por', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    empresa_id = fields.Many2one(string='Empresa', required=False, readonly=False, copy=True, store=True, comodel_name='res.company', ondelete='set null')
    instrucciones = fields.Html(string='Instrucciones', required=False, readonly=False, copy=True, store=True)
    line_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.monitoring.line', inverse_name='monitoring_id')
    state = fields.Selection(string='Barra de estado de flujo', required=False, readonly=False, copy=True, store=True, selection=[['status1', 'Ingresado'], ['status2', 'Aprobado']], default='status1')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if not values.get("name") or values["name"] == "Nuevo":
                values["name"] = self.env["ir.sequence"].next_by_code(self._folio_sequence) or "/"
        return super().create(values_list)


class StepAgriculturePhenologicalStage(models.Model):
    _inherit = 'step.agriculture.phenological.stage'
    legacy_active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True)
    cdigo_estado_fenolgico = fields.Char(string='Código estado fenológico', required=False, readonly=False, copy=True, store=True)
    species_id = fields.Many2one(string='Especie', required=False, readonly=False, copy=True, store=True, comodel_name='step.especie', ondelete='set null')
    fecha_inicio = fields.Date(string='Fecha inicio', required=False, readonly=False, copy=True, store=True)
    fecha_trmino = fields.Date(string='Fecha término', required=False, readonly=False, copy=True, store=True)
    observacin = fields.Html(string='Observación', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureApplicationMachinery(models.Model):
    _name = 'step.agriculture.application.machinery'
    _description = 'aplicacion_foliar_line'
    _rec_name = "name"
    _order = "id"
    application_id = fields.Many2one(string='X Aplicacion Foliar', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.application', ondelete='set null')
    name = fields.Char(string='Maquinada', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    aplicador_id = fields.Many2one(string='Aplicador', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    cost_center_id = fields.Many2one(string='Centro Costo', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    costo_estndar_total = fields.Float(string='Costo estándar total', required=False, readonly=True, copy=False, store=True, compute='_compute_costo_estndar_total')
    cuartel_id = fields.Many2one(string='Cuartel', required=False, readonly=False, copy=True, store=True, comodel_name='step.cuartel.line', ondelete='set null')
    fecha_hr_inicio = fields.Datetime(string='Fecha Hr Inicio', required=False, readonly=False, copy=True, store=True)
    legacy_decimal = fields.Float(string='Nuevo Decimal', required=False, readonly=False, copy=True, store=True)
    has_aplicadas = fields.Float(string='Has aplicadas', required=False, readonly=False, copy=True, store=True)
    has_cuartel = fields.Integer(string='Has cuartel', required=False, readonly=True, copy=False, store=False, compute='_compute_has_cuartel')
    hormetro_final = fields.Float(string='Horómetro final', required=False, readonly=False, copy=True, store=True)
    hormetro_inicial = fields.Float(string='Horómetro inicial', required=False, readonly=True, copy=False, store=False, related='mquina_id.odometer')
    hrs_mquina = fields.Float(string='Hrs máquina', required=False, readonly=False, copy=True, store=True)
    implemento_id = fields.Many2one(string='Implemento', required=False, readonly=False, copy=True, store=True, comodel_name='step.machinery.implement', ondelete='set null')
    labor_maquinaria_id = fields.Many2one(string='Labor maquinaria', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    lts_maquinada = fields.Float(string='Lts. mezcla aplicados', required=False, readonly=False, copy=True, store=True)
    mquina_id = fields.Many2one(string='Máquina', required=False, readonly=False, copy=True, store=True, comodel_name='fleet.vehicle', ondelete='set null')
    center_cuartel_ids = fields.One2many(string='Nuevo Campo relacionado', required=False, readonly=True, copy=False, store=False, comodel_name='step.cuartel.line', related='cost_center_id.cuartel_line')
    available_cuartel_ids = fields.One2many(string='Nuevo Campo relacionado', required=False, readonly=True, copy=False, store=False, comodel_name='step.cuartel.line', related='cost_center_id.cuartel_line')
    analytic_cuartel_ids = fields.One2many(string='Nuevo Campo relacionado', required=False, readonly=True, copy=False, store=False, comodel_name='step.cuartel.line', related='cost_center_id.cost_id.cuartel_line')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    udm_labor_id = fields.Many2one(string='UdM labor', required=False, readonly=True, copy=False, store=False, comodel_name='uom.uom', ondelete='set null', related='labor_maquinaria_id.uom_id')
    valor_st_hr_mquina = fields.Float(string='Valor St Hr máquina ', required=False, readonly=True, copy=False, store=False, related='mquina_id.step_cost_hrmq_standar')

    @api.depends('hrs_mquina', 'valor_st_hr_mquina')
    def _compute_costo_estndar_total(self):
        for record in self:
            record['costo_estndar_total'] = record.hrs_mquina * record.valor_st_hr_mquina

    @api.depends()
    def _compute_has_cuartel(self):
        for record in self:
            record['has_cuartel'] = False


class StepAgricultureApplication(models.Model):
    _inherit = 'step.agriculture.application'
    _folio_sequence = 'aplicaciones.bpa'
    name = fields.Char(default="Nuevo")
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    capacidad_lts_aplicadora = fields.Float(string='Capacidad lts aplicadora', required=False, readonly=False, copy=True, store=True)
    combustible_id = fields.Many2one(string='Combustible', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    consumo = fields.Float(string='Consumo', required=False, readonly=True, copy=False, store=True, compute='_compute_consumo')
    consumo_lt_x_hora = fields.Float(string='Consumo lt x hora', required=True, readonly=False, copy=True, store=True)
    costo_por_hectrea = fields.Float(string='Costo por hectárea', required=False, readonly=False, copy=True, store=True)
    direccin_del_viento = fields.Char(string='Dirección del viento', required=False, readonly=False, copy=True, store=True)
    empresa_id = fields.Many2one(string='Empresa', required=False, readonly=False, copy=True, store=True, comodel_name='res.company', ondelete='set null')
    forma_de_aplicar_id = fields.Many2one(string='Forma de aplicar', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.application.method', ondelete='set null')
    hrs_total_aplicacin = fields.Float(string='Hrs total aplicación', required=False, readonly=False, copy=True, store=True)
    instructions_html = fields.Html(string='Nuevo HTML', required=False, readonly=False, copy=True, store=True)
    precautions_html = fields.Html(string='Nuevo HTML', required=False, readonly=False, copy=True, store=True)
    humedad = fields.Float(string='Humedad', required=False, readonly=False, copy=True, store=True)
    instrucciones = fields.Html(string='Instrucciones', required=False, readonly=False, copy=True, store=True)
    instrucciones_1 = fields.Html(string='Instrucciones', required=False, readonly=False, copy=True, store=True)
    instrucciones_2 = fields.Html(string='Instrucciones', required=False, readonly=False, copy=True, store=True)
    litros_finales = fields.Float(string='Litros finales', required=False, readonly=False, copy=True, store=True)
    lluvia_en_24_hrs_m3 = fields.Float(string='Lluvia en 24 hrs (m3)', required=False, readonly=False, copy=True, store=True)
    lts_inicial_estanque = fields.Float(string='Lts inicial estanque', required=False, readonly=False, copy=True, store=True)
    lts_relleno = fields.Float(string='Lts relleno', required=False, readonly=False, copy=True, store=True)
    maquinadas = fields.Float(string='Maquinadas', required=False, readonly=True, copy=False, store=True, compute='_compute_maquinadas')
    mojamiento_por_h = fields.Float(string='Mojamiento por há.', required=False, readonly=False, copy=True, store=True)
    cost_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.application.cost', inverse_name='application_id')
    machinery_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.application.machinery', inverse_name='application_id')
    worker_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.application.worker', inverse_name='application_id')
    ppe_ids = fields.One2many(string=' ', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.application.ppe', inverse_name='application_id')
    product_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.application.product', inverse_name='application_id')
    waste_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.application.waste', inverse_name='application_id')
    note_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.application.note', inverse_name='application_id')
    otros = fields.Float(string='Otros', required=False, readonly=False, copy=True, store=True)
    sector_id = fields.Many2one(string='Sector', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation.sector', ondelete='set null')
    legacy_workflow_state = fields.Selection(string='Barra de estado de flujo', required=False, readonly=False, copy=True, store=True, selection=[['status1', 'Ingresado'], ['status2', 'Aprobado'], ['status3', 'Costeado'], ['Contabilizado', 'Contabilizado']])
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    t_ambiente = fields.Float(string='T° ambiente', required=False, readonly=False, copy=True, store=True)
    legacy_notes = fields.Text(string='Nuevo Texto multilínea', required=False, readonly=False, copy=True, store=True)
    tipo_de_aplicacin_id = fields.Many2one(string='Tipo de aplicación', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.application.type', ondelete='set null')
    total_hectreas_1 = fields.Float(string='Total hectáreas', required=False, readonly=False, copy=True, store=True)
    total_lts_mezca = fields.Float(string='Total Lts mezcla', required=False, readonly=True, copy=False, store=True, compute='_compute_total_lts_mezca')
    trabajador_id = fields.Many2one(string='Trabajador', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    usuario_registro_id = fields.Many2one(string='Usuario registro', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    viento_kmhr = fields.Float(string='Viento km/hr', required=False, readonly=False, copy=True, store=True)

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if not values.get("name") or values["name"] == "Nuevo":
                values["name"] = self.env["ir.sequence"].next_by_code(self._folio_sequence) or "/"
        return super().create(values_list)

    @api.depends('lts_inicial_estanque', 'lts_relleno', 'litros_finales')
    def _compute_consumo(self):
        for record in self:
            record['consumo'] = record.lts_inicial_estanque + record.lts_relleno - record.litros_finales

    @api.depends('total_hectreas', 'mojamiento_por_h', 'capacidad_lts_aplicadora')
    def _compute_maquinadas(self):
        for record in self:
            record['maquinadas'] = record.total_hectreas * record.mojamiento_por_h / record.capacidad_lts_aplicadora

    @api.depends('total_hectreas', 'mojamiento_por_h')
    def _compute_total_lts_mezca(self):
        for record in self:
            record['total_lts_mezca'] = record.total_hectreas * record.mojamiento_por_h


class StepAgricultureApplicationType(models.Model):
    _inherit = 'step.agriculture.application.type'
    legacy_active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True)
    cdigo_aplicaciones = fields.Char(string='Código aplicaciones', required=False, readonly=False, copy=True, store=True)
    observaciones = fields.Html(string='Observaciones', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureApplicationNote(models.Model):
    _name = 'step.agriculture.application.note'
    _description = 'aplicacion_foliar_line'
    _rec_name = "name"
    _order = "id"
    application_id = fields.Many2one(string='X Aplicacion Foliar', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.application', ondelete='set null')
    name = fields.Char(string='Descripción', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureApplicationWaste(models.Model):
    _name = 'step.agriculture.application.waste'
    _description = 'aplicacion_foliar_line'
    _rec_name = "name"
    _order = "id"
    application_id = fields.Many2one(string='X Aplicacion Foliar', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.application', ondelete='set null')
    name = fields.Char(string='Fecha lavado', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    agua_usada_lts = fields.Float(string='Agua usada (lts)', required=False, readonly=False, copy=True, store=True)
    cantidad_mezcla = fields.Float(string='Cantidad mezcla', required=False, readonly=False, copy=True, store=True)
    legacy_reference = fields.Char(string='X Studio Char Field 87O 1Jhu3Tihh', required=False, readonly=False, copy=True, store=True)
    comentario = fields.Char(string='Comentario', required=False, readonly=False, copy=True, store=True)
    destino_residuo = fields.Selection(string='Destino residuo', required=False, readonly=False, copy=True, store=True, selection=[['Orillado', 'Orillado'], ['Camino', 'Camino'], ['Terreno barbecho', 'Terreno barbecho'], ['Otro', 'Otro']])
    notes_html = fields.Html(string='Nuevo HTML', required=False, readonly=False, copy=True, store=True)
    observacin = fields.Integer(string='Observación', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    tipo_remanente = fields.Selection(string='Tipo remanente', required=False, readonly=False, copy=True, store=True, selection=[['Lavado máquina', 'Lavado máquina'], ['Remanente mezcla', 'Remanente mezcla']])


class StepAgricultureApplicationProduct(models.Model):
    _name = 'step.agriculture.application.product'
    _description = 'aplicacion_foliar_line'
    _rec_name = "name"
    _order = "id"
    application_id = fields.Many2one(string='X Aplicacion Foliar', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.application', ondelete='set null')
    name = fields.Char(string='Num', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    consumo_terico = fields.Float(string='Consumo teórico', required=False, readonly=False, copy=True, store=True)
    dosis_100_lts = fields.Float(string='Dosis 100 lts', required=False, readonly=False, copy=True, store=True)
    dosis_por_ha = fields.Float(string='Dosis por ha', required=False, readonly=False, copy=True, store=True)
    ds_carencia_etiqueta = fields.Integer(string='Ds carencia etiqueta', required=False, readonly=True, copy=False, store=False, related='producto_id.dia_carencia')
    ds_carencia_mayor = fields.Integer(string='Ds carencia mayor', required=False, readonly=True, copy=False, store=False, related='producto_id.x_studio_das_carencia_mayor')
    ds_carencia_ue = fields.Integer(string='Ds carencia UE', required=False, readonly=True, copy=False, store=False, related='producto_id.x_studio_das_carencia_ue')
    ds_carencia_usa = fields.Integer(string='Ds carencia USA', required=False, readonly=True, copy=False, store=False, related='producto_id.x_studio_das_carencia_usa')
    mximo_veces = fields.Integer(string='Máximo veces', required=False, readonly=True, copy=False, store=False, related='producto_id.x_studio_mximo_veces_a_aplicar')
    objetivo_plaga_id = fields.Many2one(string='Objetivo, plaga', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.pest', ondelete='set null')
    producto_id = fields.Many2one(string='Producto', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    sustancia_activa_id = fields.Many2one(string='Sustancia activa', required=False, readonly=True, copy=False, store=False, comodel_name='step.agriculture.active.ingredient', ondelete='set null', related='producto_id.sustancia_activa_id')


class StepAgricultureApplicationPpe(models.Model):
    _name = 'step.agriculture.application.ppe'
    _description = 'aplicacion_foliar_line'
    _rec_name = "name"
    _order = "id"
    application_id = fields.Many2one(string='X Aplicacion Foliar', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.application', ondelete='set null')
    name = fields.Char(string='Fecha', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    empleado_id = fields.Many2one(string='Empleado', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    epp = fields.Char(string='EPP ', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureApplicationWorker(models.Model):
    _name = 'step.agriculture.application.worker'
    _description = 'aplicacion_foliar_line'
    _rec_name = "name"
    _order = "id"
    application_id = fields.Many2one(string='X Aplicacion Foliar', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.application', ondelete='set null')
    name = fields.Char(string='Línea', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    cost_center_id = fields.Many2one(string='Centro de costos', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    costo_mo_bpa = fields.Float(string='Costo MO BPA', required=False, readonly=True, copy=False, store=True, compute='_compute_costo_mo_bpa')
    costo_por_hora = fields.Monetary(string='Costo por hora', required=False, readonly=True, copy=False, store=False, groups='hr.group_hr_user', currency_field='currency_id', related='nombre_trabajador_id.hourly_cost')
    currency_id = fields.Many2one(string='Currency', required=False, readonly=True, copy=True, store=False, comodel_name='res.currency', ondelete='set null')
    hrs_extras = fields.Float(string='Hrs. Extras', required=False, readonly=False, copy=True, store=True)
    hrs_ord_1 = fields.Float(string='Hrs. Ord.', required=False, readonly=False, copy=True, store=True)
    labor_agrcola_id = fields.Many2one(string='Labor agrícola', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    bpa_role_id = fields.Many2one(string='Cargo BPA', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.bpa.role', ondelete='set null')
    nip = fields.Char(string='NIP', required=False, readonly=True, copy=False, store=False, groups='hr.group_hr_user', related='nombre_trabajador_id.pin')
    nombre_trabajador_id = fields.Many2one(string='Nombre trabajador', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    standard_hour_cost = fields.Monetary(string='Nuevo Campo relacionado', required=False, readonly=True, copy=False, store=False, groups='hr.group_hr_user', currency_field='currency_id', related='nombre_trabajador_id.hourly_cost')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    total_hrs = fields.Float(string='Total Hrs.', required=True, readonly=False, copy=True, store=True)

    @api.depends('total_hrs', 'costo_por_hora')
    def _compute_costo_mo_bpa(self):
        for record in self:
            record['costo_mo_bpa'] = record.total_hrs * record.costo_por_hora


class StepAgricultureBpaRole(models.Model):
    _name = 'step.agriculture.bpa.role'
    _description = 'Cargos BPA'
    _rec_name = "name"
    _order = "id"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    name = fields.Char(string='Descripción', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureApplicationCost(models.Model):
    _name = 'step.agriculture.application.cost'
    _description = 'aplicacion_foliar_line'
    _rec_name = "name"
    _order = "id"
    application_id = fields.Many2one(string='X Aplicacion Foliar', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.application', ondelete='set null')
    name = fields.Char(string='Descripción', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    actividad_id = fields.Many2one(string='Actividad', required=False, readonly=False, copy=True, store=True, comodel_name='mail.activity', ondelete='set null')
    cost_center_id = fields.Many2one(string='Centro de costos', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    consumo = fields.Float(string='Consumo', required=False, readonly=False, copy=True, store=True)
    costo_total = fields.Float(string='Costo total', required=False, readonly=True, copy=False, store=True, compute='_compute_costo_total')
    costo_unitario = fields.Float(string='Costo Unitario', required=False, readonly=True, copy=False, store=False, groups='base.group_user', related='producto_id.standard_price')
    labor_agrcola_id = fields.Many2one(string='Labor agrícola', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    producto_id = fields.Many2one(string='Producto', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    udm_id = fields.Many2one(string='UdM', required=False, readonly=True, copy=False, store=False, comodel_name='uom.uom', ondelete='set null', related='producto_id.uom_id')

    @api.depends('consumo', 'costo_unitario')
    def _compute_costo_total(self):
        for record in self:
            record['costo_total'] = record.consumo * record.costo_unitario


class StepAgricultureApplicationMethod(models.Model):
    _name = 'step.agriculture.application.method'
    _description = 'Forma de aplicación'
    _rec_name = "name"
    _order = "id"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    name = fields.Char(string='Descripción', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    cdigo_forma_aplicar = fields.Char(string='Código forma aplicar', required=False, readonly=False, copy=True, store=True)
    observacin = fields.Html(string='Observación', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureHarvestRecord(models.Model):
    _name = 'step.agriculture.harvest.record'
    _description = 'Registro cosecha'
    _rec_name = "name"
    _order = "id"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _folio_sequence = 'Folio.cosecha'
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    name = fields.Char(string='Folio Cosecha', required=False, readonly=True, copy=False, store=True, default="Nuevo")
    cantidad_embalaje = fields.Float(string='Cantidad embalaje', required=False, readonly=False, copy=True, store=True)
    cantidad_kilos = fields.Datetime(string='Cantidad kilos', required=False, readonly=False, copy=True, store=True)
    cdigo_de_barra_ids = fields.Many2many(string='Código de barra', required=False, readonly=False, copy=True, store=True, comodel_name='barcode.nomenclature', relation='x_barcode_nomenclature_x_registro_cosecha_rel', column1='x_registro_cosecha_id', column2='barcode_nomenclature_id')
    cost_center_id = fields.Many2one(string='Centro costos', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    contratista_id = fields.Many2one(string='Contratista', required=False, readonly=False, copy=True, store=True, comodel_name='res.partner', ondelete='set null')
    cuadrilla = fields.Char(string='Cuadrilla', required=False, readonly=False, copy=True, store=True)
    cuartel_id = fields.Many2one(string='Cuartel', required=False, readonly=False, copy=True, store=True, comodel_name='step.cuartel.line', ondelete='set null')
    dotacin = fields.Float(string='Dotación', required=False, readonly=False, copy=True, store=True)
    embalaje_id = fields.Many2one(string='Embalaje', required=False, readonly=False, copy=True, store=True, comodel_name='product.packaging', ondelete='set null')
    species_id = fields.Many2one(string='Especie', required=False, readonly=False, copy=True, store=True, comodel_name='step.especie', ondelete='set null')
    date = fields.Datetime(string='Fecha', required=False, readonly=False, copy=True, store=True)
    harvest_date = fields.Date(string='Fecha', required=False, readonly=False, copy=True, store=True)
    fundo_id = fields.Many2one(string='Fundo', required=False, readonly=False, copy=True, store=True, comodel_name='step.fundo', ondelete='set null')
    horas_de_proceso = fields.Float(string='Horas de proceso', required=False, readonly=False, copy=True, store=True)
    kilos_cosechados = fields.Float(string='Kilos cosechados', required=False, readonly=False, copy=True, store=True)
    process_ids = fields.Many2many(string='Nuevo Etiquetas', required=False, readonly=False, copy=True, store=True, comodel_name='step.cosecha.proceso', relation='x_step_cosecha_proceso_x_registro_cosecha_rel', column1='x_registro_cosecha_id', column2='step_cosecha_proceso_id')
    tag_ids = fields.One2many(string='Cantidad tarjas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.harvest.tag', inverse_name='harvest_id')
    pasada = fields.Char(string='Pasada', required=False, readonly=False, copy=True, store=True)
    producto_cosechado_id = fields.Many2one(string='Producto cosechado', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    supervisor_id = fields.Many2one(string='Supervisor', required=False, readonly=False, copy=True, store=True, comodel_name='hr.employee', ondelete='set null')
    tarja_cosecha = fields.Char(string='Tarja cosecha', required=False, readonly=False, copy=True, store=True)
    temporada_id = fields.Many2one(string='Temporada', required=False, readonly=False, copy=True, store=True, comodel_name='step.temporada', ondelete='set null')
    tipo_cosecha = fields.Char(string='Tipo Cosecha', required=False, readonly=False, copy=True, store=True)
    tipo_cosecha_1 = fields.Selection(string='Tipo cosecha', required=False, readonly=False, copy=True, store=True, selection=[['Exportación', 'Exportación'], ['Industrial', 'Industrial'], ['Comercial', 'Comercial']])
    tipo_tarea_id = fields.Many2one(string='Tipo Tarea', required=False, readonly=False, copy=True, store=True, comodel_name='project.task', ondelete='set null')
    tipo_tareo = fields.Selection(string='Tipo Tareo', required=False, readonly=False, copy=True, store=True, selection=[['Propia', 'Propia'], ['Contratista', 'Contratista']])
    total_horas = fields.Float(string='Total horas', required=False, readonly=False, copy=True, store=True)
    ubicacin_operacin_id = fields.Many2one(string='Ubicación operación', required=False, readonly=False, copy=True, store=True, comodel_name='step.cosecha.ubicacion', ondelete='set null')
    variety_id = fields.Many2one(string='Variedad', required=False, readonly=False, copy=True, store=True, comodel_name='step.variedad', ondelete='set null')

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if not values.get("name") or values["name"] == "Nuevo":
                values["name"] = self.env["ir.sequence"].next_by_code(self._folio_sequence) or "/"
        return super().create(values_list)


class StepAgricultureHarvestTag(models.Model):
    _name = 'step.agriculture.harvest.tag'
    _description = 'registro_cosecha_line'
    _rec_name = "name"
    _order = "id"
    name = fields.Char(string='Num tarja cosecha', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    harvest_id = fields.Many2one(string='X Registro Cosecha', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.harvest.record', ondelete='set null')
    barcode_id = fields.Many2one(string='barcode', required=False, readonly=False, copy=True, store=True, comodel_name='barcode.nomenclature', ondelete='set null')
    cantidad_envases = fields.Float(string='Cantidad envases', required=False, readonly=False, copy=True, store=True)
    cdigo_de_barra_ids = fields.Many2many(string='Código de barra', required=False, readonly=False, copy=True, store=True, comodel_name='barcode.rule', relation='x_barcode_rule_x_registro_cosecha_line_7dde6_rel', column1='x_registro_cosecha_line_7dde6_id', column2='barcode_rule_id')
    envase_id = fields.Many2one(string='Envase', required=False, readonly=False, copy=True, store=True, comodel_name='product.packaging', ondelete='set null')
    legacy_tag_state_id = fields.Many2one(string='Estado tarja', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.archive.tag.state', ondelete='set null')
    kilos_cosechados = fields.Float(string='Kilos cosechados', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    tipo_de_paquete_id = fields.Many2one(string='Tipo de paquete', required=False, readonly=False, copy=True, store=True, comodel_name='stock.package.type', ondelete='set null')
    tipo_paquete_id = fields.Many2one(string='Tipo Paquete', required=False, readonly=False, copy=True, store=True, comodel_name='stock.quant.package', ondelete='set null')


class StepAgricultureArchiveTagState(models.Model):
    _name = 'step.agriculture.archive.tag.state'
    _description = 'Estado de tarjas'
    _rec_name = "name"
    _order = "id"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    name = fields.Char(string='Descripción', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    code = fields.Char(string='Código estado tarja', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureHarvestForecast(models.Model):
    _name = 'step.agriculture.harvest.forecast'
    _description = 'Planificar cosecha'
    _rec_name = "name"
    _order = "id"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    name = fields.Char(string='Descripción', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    cost_center_id = fields.Many2one(string='Centro costos', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    envase_cosecha_id = fields.Many2one(string='Envase cosecha', required=False, readonly=False, copy=True, store=True, comodel_name='product.packaging', ondelete='set null')
    envases_totales_estimados = fields.Float(string='Envases totales estimados', required=False, readonly=False, copy=True, store=True)
    species_id = fields.Many2one(string='Especie', required=False, readonly=False, copy=True, store=True, comodel_name='step.especie', ondelete='set null')
    fecha_fin_cosecha = fields.Date(string='Fecha fin cosecha', required=False, readonly=True, copy=False, store=False, related='cost_center_id.date_end_co')
    fecha_inicio_cosecha = fields.Date(string='Fecha Inicio cosecha', required=False, readonly=True, copy=False, store=False, related='cost_center_id.date_init_co')
    fundo_id = fields.Many2one(string='Fundo', required=False, readonly=False, copy=True, store=True, comodel_name='step.fundo', ondelete='set null')
    has_cuartel = fields.Integer(string='Has cuartel', required=False, readonly=True, copy=False, store=False, compute='_compute_has_cuartel')
    jornadas_totales_estimadas = fields.Float(string='Jornadas totales estimadas', required=False, readonly=False, copy=True, store=True)
    kg_por_envase = fields.Float(string='Kg por envase', required=False, readonly=False, copy=True, store=True)
    kg_por_hectrea = fields.Float(string='Kg por hectárea', required=False, readonly=False, copy=True, store=True)
    kg_totales_estimados = fields.Float(string='Kg totales estimados', required=False, readonly=False, copy=True, store=True)
    kilos_por_planta = fields.Float(string='Cantidad UdM estimación -planta', required=False, readonly=False, copy=True, store=True)
    variety_id = fields.Many2one(string='Variedad', required=False, readonly=False, copy=True, store=True, comodel_name='step.variedad', ondelete='set null')
    cuartel_id = fields.Many2one(string='Cuartel', required=False, readonly=False, copy=True, store=True, comodel_name='step.cuartel.line', ondelete='set null')
    peso_udm_estimacin = fields.Float(string='Peso UdM estimación', required=False, readonly=False, copy=True, store=True)
    plantas_cuartel = fields.Integer(string='Plantas cuartel', required=False, readonly=True, copy=False, store=False, related='cost_center_id.cuartel_line.plant_cuartel')
    rendimiento_jornada = fields.Float(string='Rendimiento jornada', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    udm_estimacin = fields.Selection(string='UdM estimación', required=False, readonly=False, copy=True, store=True, selection=[['Kilo', 'Kilo'], ['Frutos', 'Frutos'], ['Racimo', 'Racimo']])

    @api.depends()
    def _compute_has_cuartel(self):
        for record in self:
            record['has_cuartel'] = False


class StepAgricultureIrrigation(models.Model):
    _inherit = 'step.agriculture.irrigation'
    active = fields.Boolean(string='Activo', required=False, readonly=False, copy=True, store=True, default=True)
    empresa_id = fields.Many2one(string='Empresa', required=False, readonly=False, copy=True, store=True, comodel_name='res.company', ondelete='set null')
    estanque_riego_id = fields.Many2one(string='Estanque riego', required=False, readonly=False, copy=True, store=True, comodel_name='step.machinery.implement', ondelete='set null')
    forma_de_aplicar_id = fields.Many2one(string='Forma de aplicar', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.application.method', ondelete='set null')
    instrucciones = fields.Html(string='Instrucciones', required=False, readonly=False, copy=True, store=True)
    instrucciones_1 = fields.Html(string='Instrucciones', required=False, readonly=False, copy=True, store=True)
    cost_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.irrigation.cost', inverse_name='irrigation_id')
    product_ids = fields.One2many(string='Producto', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.irrigation.product', inverse_name='irrigation_id')
    schedule_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.irrigation.schedule', inverse_name='irrigation_id')
    recipe_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.irrigation.recipe', inverse_name='irrigation_id')
    water_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.irrigation.water', inverse_name='irrigation_id')
    state = fields.Selection(string='Barra de estado de flujo', required=False, readonly=False, copy=True, store=True, selection=[['status1', 'Ingresado'], ['status2', 'Ejecutado'], ['status3', 'Aprobado']], default='status1')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    tipo_mezcla = fields.Selection(string='Tipo mezcla', required=False, readonly=False, copy=True, store=True, selection=[['Sólo riego', 'Sólo riego'], ['Riego y fertilización', 'Riego y fertilización']])


class StepAgricultureIrrigationWater(models.Model):
    _name = 'step.agriculture.irrigation.water'
    _description = 'riego_y_fertilizacio_line'
    _rec_name = "name"
    _order = "id"
    name = fields.Char(string='Día semana', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    irrigation_id = fields.Many2one(string='X Riego Y Fertilizacio', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation', ondelete='set null')
    cost_center_id = fields.Many2one(string='Centro costos', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    cuartel_id = fields.Many2one(string='Cuartel', required=False, readonly=False, copy=True, store=True, comodel_name='step.cuartel.line', ondelete='set null')
    has_centro_costo = fields.Integer(string='Has centro costo', required=False, readonly=True, copy=False, store=False, compute='_compute_has_centro_costo')
    has_cuartel = fields.Integer(string='Has cuartel', required=False, readonly=True, copy=False, store=False, compute='_compute_has_cuartel')
    litros_de_agua = fields.Float(string='Litros de agua', required=False, readonly=False, copy=True, store=True)
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    vlvula_id = fields.Many2one(string='Válvula', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation.valve', ondelete='set null')

    @api.depends()
    def _compute_has_centro_costo(self):
        for record in self:
            record['has_centro_costo'] = False

    @api.depends()
    def _compute_has_cuartel(self):
        for record in self:
            record['has_cuartel'] = False


class StepAgricultureIrrigationRecipe(models.Model):
    _name = 'step.agriculture.irrigation.recipe'
    _description = 'riego_y_fertilizacio_line'
    _rec_name = "name"
    _order = "id"
    name = fields.Char(string='Descripción', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    irrigation_id = fields.Many2one(string='X Riego Y Fertilizacio', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation', ondelete='set null')
    line_ids = fields.One2many(string='Nuevas líneas', required=False, readonly=False, copy=False, store=True, comodel_name='step.agriculture.irrigation.recipe.line', inverse_name='recipe_id')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)


class StepAgricultureIrrigationRecipeLine(models.Model):
    _name = 'step.agriculture.irrigation.recipe.line'
    _description = 'riego_y_fertilizacio_line_b7eaf_line'
    _rec_name = "name"
    _order = "id"
    name = fields.Char(string='Linea', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    recipe_id = fields.Many2one(string='X Riego Y Fertilizacio Line B7Eaf', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation.recipe', ondelete='set null')
    dosis_x_100_ml = fields.Float(string='Dosis x 100 ml', required=False, readonly=False, copy=True, store=True)
    dosis_x_ha = fields.Float(string='Dosis x ha', required=False, readonly=False, copy=True, store=True)
    producto_id = fields.Many2one(string='Producto', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    udm = fields.Char(string='UdM', required=False, readonly=True, copy=False, store=False, related='producto_id.uom_id.name')


class StepAgricultureIrrigationSchedule(models.Model):
    _name = 'step.agriculture.irrigation.schedule'
    _description = 'riego_y_fertilizacio_line'
    _rec_name = "name"
    _order = "id"
    name = fields.Char(string='Día semana', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    irrigation_id = fields.Many2one(string='X Riego Y Fertilizacio', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation', ondelete='set null')
    centro_de_costo_id = fields.Many2one(string='Centro de costo', required=False, readonly=False, copy=True, store=True, comodel_name='step.centro.costo', ondelete='set null')
    centro_de_costo_1_id = fields.Many2one(string='Centro de costo', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    fecha_hr_inicio = fields.Datetime(string='Fecha Hr Inicio', required=False, readonly=False, copy=True, store=True)
    fecha_hr_trmino = fields.Datetime(string='Fecha Hr Término', required=False, readonly=False, copy=True, store=True)
    has_ccosto = fields.Integer(string='Has CCosto', required=False, readonly=True, copy=False, store=False, compute='_compute_has_ccosto')
    has_centro_costo = fields.Integer(string='Has centro costo', required=False, readonly=True, copy=False, store=False, compute='_compute_has_centro_costo')
    has_cuartel_riego = fields.Integer(string='Has cuartel riego', required=False, readonly=True, copy=False, store=False, compute='_compute_has_cuartel_riego')
    horas_riego = fields.Float(string='Horas riego', required=False, readonly=False, copy=True, store=True)
    litros_riego = fields.Float(string='Litros riego', required=False, readonly=False, copy=True, store=True)
    sector_riego_id = fields.Many2one(string='Sector riego', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation.sector', ondelete='set null')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    vlvula_id = fields.Many2one(string='Válvula', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation.valve', ondelete='set null')
    vlvula_de_riego = fields.Char(string='Válvula de riego', required=False, readonly=False, copy=True, store=True)

    @api.depends()
    def _compute_has_ccosto(self):
        for record in self:
            record['has_ccosto'] = False

    @api.depends()
    def _compute_has_centro_costo(self):
        for record in self:
            record['has_centro_costo'] = False

    @api.depends()
    def _compute_has_cuartel_riego(self):
        for record in self:
            record['has_cuartel_riego'] = False


class StepAgricultureIrrigationProduct(models.Model):
    _name = 'step.agriculture.irrigation.product'
    _description = 'riego_y_fertilizacio_line'
    _rec_name = "name"
    _order = "id"
    name = fields.Char(string='Línea', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    irrigation_id = fields.Many2one(string='X Riego Y Fertilizacio', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation', ondelete='set null')
    cantidad_producto = fields.Float(string='Cantidad producto', required=False, readonly=False, copy=True, store=True)
    dosis_x_1000_lt = fields.Float(string='Dosis x 1000 lt', required=False, readonly=False, copy=True, store=True)
    dosis_x_ha = fields.Float(string='Dosis x ha', required=False, readonly=False, copy=True, store=True)
    hectreas_a_regar = fields.Float(string='Hectáreas a regar', required=False, readonly=False, copy=True, store=True)
    horas_estimadas = fields.Float(string='Horas estimadas', required=False, readonly=False, copy=True, store=True)
    litros_mezcla = fields.Float(string='Litros mezcla', required=False, readonly=False, copy=True, store=True)
    producto_id = fields.Many2one(string='Producto', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)
    udm = fields.Char(string='UdM', required=False, readonly=True, copy=False, store=False, related='producto_id.uom_id.name')


class StepAgricultureIrrigationCost(models.Model):
    _name = 'step.agriculture.irrigation.cost'
    _description = 'riego_y_fertilizacio_line'
    _rec_name = "name"
    _order = "id"
    name = fields.Char(string='Día semana', required=True, readonly=False, copy=True, store=True, translate=True, default="Nuevo")
    irrigation_id = fields.Many2one(string='X Riego Y Fertilizacio', required=False, readonly=False, copy=True, store=True, comodel_name='step.agriculture.irrigation', ondelete='set null')
    cantidad = fields.Float(string='Cantidad', required=False, readonly=False, copy=True, store=True)
    centro_de_costo_id = fields.Many2one(string='Centro de costo', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.account', ondelete='set null')
    costo_producto = fields.Float(string='Costo producto', required=False, readonly=True, copy=False, store=False, groups='base.group_user', related='producto_id.standard_price')
    costo_total = fields.Float(string='Costo total', required=False, readonly=False, copy=True, store=True)
    distribucin_analtica_id = fields.Many2one(string='Distribución analítica', required=False, readonly=False, copy=True, store=True, comodel_name='account.analytic.distribution.model', ondelete='set null')
    has_ccosto = fields.Integer(string='Has CCosto', required=False, readonly=True, copy=False, store=False, compute='_compute_has_ccosto')
    producto_id = fields.Many2one(string='Producto', required=False, readonly=False, copy=True, store=True, comodel_name='product.template', ondelete='set null')
    product_uom_id = fields.Many2one(string='UdM', required=False, readonly=True, copy=False, store=False, comodel_name='uom.uom', ondelete='set null', related='producto_id.uom_id')
    sequence = fields.Integer(string='Secuencia', required=False, readonly=False, copy=True, store=True)

    @api.depends()
    def _compute_has_ccosto(self):
        for record in self:
            record['has_ccosto'] = False

