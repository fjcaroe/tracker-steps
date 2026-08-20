# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

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


class StepTrackerActivity(models.Model):
    _name = 'step.tracker.activity'
    _description = 'Actividad de Web Tracker (sincronizada)'
    _order = 'name'

    tracker_id = fields.Integer(string='ID en Web Tracker', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código')
    active = fields.Boolean(string='Activa en Web Tracker', default=True)
    last_sync = fields.Datetime(string='Última sincronización')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)

    _sql_constraints = [
        ('tracker_id_company_uniq', 'unique(tracker_id, company_id)',
         'Esta actividad ya está sincronizada para esta empresa.'),
    ]


class StepTrackerLabor(models.Model):
    _name = 'step.tracker.labor'
    _description = 'Labor de Web Tracker (sincronizada)'
    _order = 'name'

    tracker_id = fields.Integer(string='ID en Web Tracker', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código')
    activity_id = fields.Many2one('step.tracker.activity', string='Actividad')
    activity_tracker_id = fields.Integer(string='ID actividad en Tracker')
    effort_factor = fields.Float(string='Factor de esfuerzo')
    target_speed_kmh = fields.Float(string='Velocidad objetivo (km/h)')
    active = fields.Boolean(string='Activa en Web Tracker', default=True)
    last_sync = fields.Datetime(string='Última sincronización')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)

    _sql_constraints = [
        ('tracker_id_company_uniq', 'unique(tracker_id, company_id)',
         'Esta labor ya está sincronizada para esta empresa.'),
    ]


class StepTrackerImplement(models.Model):
    _name = 'step.tracker.implement'
    _description = 'Implemento de Web Tracker (sincronizado)'
    _order = 'name'

    tracker_id = fields.Integer(string='ID en Web Tracker', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(string='Activo en Web Tracker', default=True)
    last_sync = fields.Datetime(string='Última sincronización')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)

    _sql_constraints = [
        ('tracker_id_company_uniq', 'unique(tracker_id, company_id)',
         'Este implemento ya está sincronizado para esta empresa.'),
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
    season = fields.Char(string='Temporada')
    machine_id = fields.Many2one('step.tracker.machine', string='Máquina')
    activity_id = fields.Many2one('step.tracker.activity', string='Actividad')
    labor_id = fields.Many2one('step.tracker.labor', string='Labor')
    implement_id = fields.Many2one('step.tracker.implement', string='Implemento')
    field_id = fields.Many2one('step.tracker.field', string='Predio')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Centro de costo')
    notes = fields.Text(string='Observaciones')
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

    @api.model
    def get_dashboard_data(self, days=30):
        """Return a compact, company-aware snapshot for the Odoo dashboard."""
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 30
        days = min(max(days, 1), 3650)
        company = self.env.company
        cutoff = fields.Datetime.now() - relativedelta(days=days)
        session_domain = [
            ('company_id', '=', company.id),
            ('started_at', '>=', cutoff),
        ]
        work_order_domain = [
            ('company_id', '=', company.id),
            ('work_date', '>=', cutoff.date()),
        ]

        session_model = self.env['step.tracker.session']
        session_totals = session_model.read_group(
            session_domain,
            ['total_distance_km:sum', 'duration_hours:sum'],
            [],
        )[0]
        work_order_model = self.env['step.tracker.work_order']
        work_order_totals = work_order_model.read_group(
            work_order_domain,
            ['fuel_refill_liters:sum'],
            [],
        )[0]

        machine_groups = session_model.read_group(
            session_domain,
            ['machine_id', 'total_distance_km:sum', 'duration_hours:sum'],
            ['machine_id'],
            orderby='total_distance_km desc',
            limit=6,
        )
        top_machines = []
        # Sesiones recién iniciadas o importadas pueden tener distancia 0.
        # Mantener un denominador mínimo evita romper todo el tablero mientras
        # todavía no existen recorridos medibles.
        maximum_distance = max([
            1.0,
            *[group.get('total_distance_km', 0.0) or 0.0 for group in machine_groups],
        ])
        for group in machine_groups:
            machine_value = group.get('machine_id')
            top_machines.append({
                'id': machine_value[0] if machine_value else False,
                'name': machine_value[1] if machine_value else _('Sin máquina'),
                'distance_km': round(group.get('total_distance_km', 0.0) or 0.0, 1),
                'hours': round(group.get('duration_hours', 0.0) or 0.0, 1),
                'share': round((group.get('total_distance_km', 0.0) or 0.0) / maximum_distance * 100),
            })

        recent_sessions = []
        for session in session_model.search(session_domain, order='started_at desc', limit=6):
            recent_sessions.append({
                'id': session.id,
                'tracker_id': session.tracker_id,
                'machine': session.machine_id.name or _('Sin máquina'),
                'driver': session.driver_id.name or _('Sin conductor'),
                'started_at': fields.Datetime.to_string(session.started_at),
                'distance_km': round(session.total_distance_km or 0.0, 1),
                'status': session.status,
                'status_label': dict(session._fields['status'].selection).get(session.status, session.status),
            })

        latest_sync = self.env['step.tracker.sync.log'].search(
            [('company_id', '=', company.id)],
            order='started_at desc',
            limit=1,
        )
        return {
            'period_days': days,
            'company_name': company.name,
            'kpis': {
                'sessions': session_model.search_count(session_domain),
                'open_sessions': session_model.search_count(session_domain + [('status', '=', 'open')]),
                'distance_km': round(session_totals.get('total_distance_km', 0.0) or 0.0, 1),
                'hours': round(session_totals.get('duration_hours', 0.0) or 0.0, 1),
                'work_orders': work_order_model.search_count(work_order_domain),
                'fuel_refill_liters': round(work_order_totals.get('fuel_refill_liters', 0.0) or 0.0, 1),
                'machines': self.env['step.tracker.machine'].search_count([
                    ('company_id', '=', company.id), ('active', '=', True),
                ]),
                'drivers': self.env['step.tracker.driver'].search_count([
                    ('company_id', '=', company.id), ('active', '=', True),
                ]),
            },
            'top_machines': top_machines,
            'recent_sessions': recent_sessions,
            'latest_sync': {
                'status': latest_sync.status,
                'started_at': fields.Datetime.to_string(latest_sync.started_at) if latest_sync else False,
                'message': latest_sync.message or '',
            } if latest_sync else False,
        }
