# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class StepTracker(models.Model):
    _name = 'step.tracker'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=False, default=lambda self: self.env.company)
    note = fields.Html(string="Notas")


# ---------------------------------------------------------------------------
# Espejos de solo lectura de la app Web Tracker (monitoreo GPS de tractores).
#
# Web Tracker tiene su propia base Postgres y una API FastAPI propia; no
# comparte base de datos con Odoo. Estos modelos guardan una copia local
# liviana (maestros + operación reciente) traída por step.tracker.sync
# (ver step_tracker_sync.py), para poder consultarla desde Odoo sin entrar
# al sitio de Web Tracker. No se replica el detalle de puntos GPS: para ver
# el mapa/recorrido en detalle se linkea de vuelta a Web Tracker.
# ---------------------------------------------------------------------------

class StepTrackerMachine(models.Model):
    _name = 'step.tracker.machine'
    _description = 'Máquina de Web Tracker (sincronizada)'
    _order = 'name'

    tracker_id = fields.Integer(string='ID en Web Tracker', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    plate = fields.Char(string='Patente')
    external_id = fields.Char(string='ID externo')
    active = fields.Boolean(string='Activa en Web Tracker', default=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo Odoo',
                                  help='Vínculo opcional con la ficha de flota de Odoo.')
    tank_capacity_liters = fields.Float(string='Capacidad estanque (L)')
    fuel_consumption_lph = fields.Float(string='Consumo (L/h)')
    fuel_consumption_lpkm = fields.Float(string='Consumo (L/km)')
    last_sync = fields.Datetime(string='Última sincronización')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)

    _sql_constraints = [
        ('tracker_id_company_uniq', 'unique(tracker_id, company_id)',
         'Esta máquina ya está sincronizada para esta empresa.'),
    ]


class StepTrackerDriver(models.Model):
    _name = 'step.tracker.driver'
    _description = 'Conductor de Web Tracker (sincronizado)'
    _order = 'name'

    tracker_id = fields.Integer(string='ID en Web Tracker', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    rut = fields.Char(string='RUT')
    active = fields.Boolean(string='Activo en Web Tracker', default=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado Odoo',
                                   help='Vínculo opcional con la ficha del empleado en Odoo.')
    last_sync = fields.Datetime(string='Última sincronización')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)

    _sql_constraints = [
        ('tracker_id_company_uniq', 'unique(tracker_id, company_id)',
         'Este conductor ya está sincronizado para esta empresa.'),
    ]


class StepTrackerField(models.Model):
    _name = 'step.tracker.field'
    _description = 'Predio/polígono de Web Tracker (sincronizado)'
    _order = 'name'

    tracker_id = fields.Integer(string='ID en Web Tracker', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    color = fields.Char(string='Color')
    cost_center_tracker_id = fields.Integer(string='ID centro de costo en Tracker')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Centro de costo Odoo',
                                           help='Vínculo opcional con el centro de costo real en Odoo.')
    polygon_json = fields.Text(string='Polígono (GeoJSON, solo lectura)')
    last_sync = fields.Datetime(string='Última sincronización')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)

    _sql_constraints = [
        ('tracker_id_company_uniq', 'unique(tracker_id, company_id)',
         'Este predio ya está sincronizado para esta empresa.'),
    ]


class StepTrackerSession(models.Model):
    _name = 'step.tracker.session'
    _description = 'Sesión de trabajo (recorrido GPS) de Web Tracker'
    _order = 'started_at desc'
    _rec_name = 'tracker_id'

    tracker_id = fields.Char(string='ID en Web Tracker', required=True, index=True)
    machine_id = fields.Many2one('step.tracker.machine', string='Máquina')
    driver_id = fields.Many2one('step.tracker.driver', string='Conductor')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Centro de costo')
    started_at = fields.Datetime(string='Inicio', required=True)
    ended_at = fields.Datetime(string='Término')
    status = fields.Selection([('open', 'Abierta'), ('closed', 'Cerrada')], string='Estado', default='open')
    total_distance_km = fields.Float(string='Distancia (km)')
    avg_speed_kmh = fields.Float(string='Velocidad media (km/h)')
    points_count = fields.Integer(string='Puntos GPS')
    work_order_tracker_id = fields.Integer(string='ID parte en Tracker')
    duration_hours = fields.Float(string='Duración (h)', compute='_compute_duration_hours', store=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)

    @api.depends('started_at', 'ended_at')
    def _compute_duration_hours(self):
        for rec in self:
            if rec.started_at and rec.ended_at:
                rec.duration_hours = (rec.ended_at - rec.started_at).total_seconds() / 3600.0
            else:
                rec.duration_hours = 0.0

    _sql_constraints = [
        ('tracker_id_company_uniq', 'unique(tracker_id, company_id)',
         'Esta sesión ya está sincronizada para esta empresa.'),
    ]


class StepTrackerWorkOrder(models.Model):
    _name = 'step.tracker.work_order'
    _description = 'Parte diario de Web Tracker (sincronizado)'
    _order = 'work_date desc'
    _rec_name = 'code'

    tracker_id = fields.Integer(string='ID en Web Tracker', required=True, index=True)
    code = fields.Char(string='Código')
    work_date = fields.Date(string='Fecha')
    machine_id = fields.Many2one('step.tracker.machine', string='Máquina')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Centro de costo')
    hourmeter_initial = fields.Float(string='Horómetro inicial')
    hourmeter_final = fields.Float(string='Horómetro final')
    fuel_tank_start_liters = fields.Float(string='Estanque inicial (L)')
    fuel_tank_end_liters = fields.Float(string='Estanque final (L)')
    fuel_refill_liters = fields.Float(string='Combustible recargado (L)')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)

    _sql_constraints = [
        ('tracker_id_company_uniq', 'unique(tracker_id, company_id)',
         'Este parte ya está sincronizado para esta empresa.'),
    ]