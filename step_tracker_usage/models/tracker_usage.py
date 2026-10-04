from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StepTrackerUsage(models.Model):
    """Hecho de uso: una sesión cerrada de Tracker, una sola vez por compañía.

    Es la fuente de cantidades operativas (kilómetros, horas, lecturas de horómetro).
    Los documentos (líneas de rendición) solo *referencian* este hecho: que una sesión
    respalde dos documentos no duplica su kilometraje en los agregados, que siempre se
    calculan desde esta tabla.
    """
    _name = 'step.tracker.usage'
    _description = 'Uso de vehículo según Tracker (sesión)'
    _order = 'started_at desc, id desc'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Empresa', required=True, index=True,
                                 default=lambda self: self.env.company)
    session_uuid = fields.Char(string='Sesión en Tracker', required=True, index=True, readonly=True)
    machine_id = fields.Many2one('step.tracker.machine', string='Máquina Tracker', check_company=True, index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', related='machine_id.vehicle_id',
                                 store=True, index=True)
    driver_id = fields.Many2one('step.tracker.driver', string='Conductor Tracker', check_company=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado conductor', related='driver_id.employee_id',
                                  store=True, index=True)
    cost_center_id = fields.Many2one('step.tracker.cost_center', string='Centro de costo Tracker',
                                     check_company=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Cuenta analítica',
                                          related='cost_center_id.analytic_account_id', store=True, index=True)
    started_at = fields.Datetime(string='Inicio', required=True, index=True)
    ended_at = fields.Datetime(string='Término', index=True)
    status = fields.Selection([('open', 'Abierta'), ('closed', 'Cerrada')], string='Estado', default='open')
    is_closed_fact = fields.Boolean(string='Hecho cerrado válido', compute='_compute_is_closed_fact', store=True, index=True)
    duration_hours = fields.Float(string='Duración de la sesión (h)', compute='_compute_duration_hours', store=True)
    points_count = fields.Integer(string='Puntos GPS')
    # Distancia GPS. La API la entrega en metros; aquí se guarda en km (conversión única).
    distance_km = fields.Float(string='Distancia GPS (km)', digits=(16, 4))
    distance_known = fields.Boolean(string='Distancia GPS disponible')
    # Lecturas del parte diario asociado. Solo son válidas con hourmeter_known.
    work_order_tracker_id = fields.Integer(string='ID parte en Tracker')
    work_order_code = fields.Char(string='Parte diario')
    work_order_session_count = fields.Integer(string='Sesiones del mismo parte', compute='_compute_work_order_session_count')
    hourmeter_initial = fields.Float(string='Horómetro inicial', digits=(16, 2))
    hourmeter_final = fields.Float(string='Horómetro final', digits=(16, 2))
    hourmeter_known = fields.Boolean(string='Horómetro registrado')
    fuel_refill_liters = fields.Float(string='Recarga registrada en el parte (L)', digits=(16, 2))
    fuel_refill_known = fields.Boolean(string='Recarga registrada')
    estimated_fuel_liters = fields.Float(
        string='Combustible estimado (L)', digits=(16, 2),
        help='Estimación de Tracker (consumo de la máquina). No es combustible comprado ni consumo medido.')
    synced_at = fields.Datetime(string='Sincronizado', readonly=True)
    unresolved_reason = fields.Char(string='Vínculos sin resolver', compute='_compute_unresolved_reason', store=True)

    _sql_constraints = [
        ('session_company_uniq', 'unique(session_uuid, company_id)',
         'Esta sesión de Tracker ya existe para esta empresa.'),
        ('distance_not_negative', 'check(distance_km >= 0)', 'La distancia no puede ser negativa.'),
    ]

    @api.depends('status', 'started_at', 'ended_at')
    def _compute_is_closed_fact(self):
        for rec in self:
            rec.is_closed_fact = bool(
                rec.status == 'closed' and rec.started_at and rec.ended_at and rec.ended_at >= rec.started_at)

    @api.depends('started_at', 'ended_at')
    def _compute_duration_hours(self):
        for rec in self:
            if rec.started_at and rec.ended_at and rec.ended_at >= rec.started_at:
                rec.duration_hours = (rec.ended_at - rec.started_at).total_seconds() / 3600.0
            else:
                rec.duration_hours = 0.0

    def _compute_work_order_session_count(self):
        for rec in self:
            rec.work_order_session_count = self.sudo().search_count([
                ('company_id', '=', rec.company_id.id),
                ('work_order_tracker_id', '=', rec.work_order_tracker_id),
            ]) if rec.work_order_tracker_id else 0

    @api.depends('machine_id', 'machine_id.vehicle_id', 'driver_id', 'driver_id.employee_id', 'cost_center_id',
                 'cost_center_id.analytic_account_id')
    def _compute_unresolved_reason(self):
        for rec in self:
            reasons = []
            if not rec.machine_id:
                reasons.append(_('Máquina sin registro en Odoo'))
            elif not rec.machine_id.vehicle_id:
                reasons.append(_('Máquina sin vehículo Odoo asociado'))
            if not rec.driver_id:
                reasons.append(_('Conductor no identificado en la sesión'))
            elif not rec.driver_id.employee_id:
                reasons.append(_('Conductor sin empleado Odoo asociado'))
            if not rec.cost_center_id:
                reasons.append(_('Sesión sin centro de costo en Tracker'))
            elif not rec.cost_center_id.analytic_account_id:
                reasons.append(_('Centro de costo sin cuenta analítica vinculada'))
            rec.unresolved_reason = '; '.join(reasons) or False

    @api.constrains('ended_at', 'started_at')
    def _check_dates(self):
        for rec in self:
            if rec.ended_at and rec.started_at and rec.ended_at < rec.started_at:
                raise ValidationError(_('El término de la sesión no puede ser anterior a su inicio.'))

    # ------------------------------------------------------------------
    # Consulta por período
    # ------------------------------------------------------------------
    @api.model
    def _period_domain(self, date_from, date_to):
        """Dominio de sesiones que tocan [date_from, date_to) (datetimes UTC naive)."""
        return [
            ('started_at', '<', date_to),
            '|', ('ended_at', '=', False), ('ended_at', '>=', date_from),
        ]

    def _data_issues(self):
        """Motivos por los que un hecho no es un uso cerrado y completo. Lista vacía = sin observaciones."""
        self.ensure_one()
        issues = []
        if self.status != 'closed' or not self.ended_at:
            issues.append(_('Sesión abierta o sin término'))
        if not self.distance_known:
            issues.append(_('Sin distancia GPS'))
        return issues
