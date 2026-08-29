# -*- coding: utf-8 -*-

import uuid

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StepMoviRegistry(models.Model):
    """Viaje de movilización de personal. Modelo/tabla conservados desde
    step_hr (step.movi.registry / step_movi_registry) para no perder
    historial; la lógica de costeo/contabilización fue corregida contra los
    riesgos detectados en la auditoría (ver docs/movilizacion)."""
    _name = 'step.movi.registry'
    _inherit = ['mail.thread']
    _description = 'Viaje de movilización'
    _order = 'date desc, id desc'

    name = fields.Char(string='Número', index=True, required=True, copy=False,
                        readonly=True, default=lambda self: _('Nuevo'))
    uuid = fields.Char(string='UUID externo', copy=False, readonly=True, index=True,
                        default=lambda self: str(uuid.uuid4()))
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    scheduled_time = fields.Datetime(string='Hora programada')
    actual_start = fields.Datetime(string='Inicio real')
    actual_end = fields.Datetime(string='Término real')
    tz = fields.Selection(selection='_selection_tz', string='Zona horaria',
                           default=lambda self: self.env.company.partner_id.tz or 'America/Santiago')
    recorrido_id = fields.Many2one('hr.route', 'Recorrido', required=True, tracking=True)
    direction = fields.Selection(
        selection=[('ida', 'Ida'), ('vuelta', 'Regreso'), ('ida_vuelta', 'Ida y regreso')],
        string='Sentido', required=True, default='ida', tracking=True)
    vehicle_id = fields.Many2one('fleet.vehicle', 'Vehículo', required=True, tracking=True)
    responsable_id = fields.Many2one('res.users', 'Responsable', default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', 'Transportista', required=True, tracking=True,
                                  domain=[('step_trans_person', '=', True)])
    chofer_id = fields.Many2one('res.partner', 'Chofer', required=True, tracking=True,
                                 domain=[('step_chofer', '=', True)])
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Lista de tarifa',
        domain="[('moviliza', '=', True), ('transporte_id', '=', partner_id)]",
        help='Filtrada por el campo "Transportista" propio de Movilización '
             '(transporte_id), no por el "Contratista" genérico compartido con otros '
             'dominios — ver docs/movilizacion/02_ARQUITECTURA_Y_DECISIONES.md §product.pricelist.')
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                  default=lambda self: self.env.company)
    note = fields.Html(string="Notas")
    origin = fields.Selection(
        selection=[('manual', 'Manual'), ('mobile', 'App móvil'), ('imported', 'Importado')],
        string='Origen', default='manual', required=True, copy=False)

    movi_line = fields.One2many('step.movi.registry.line', 'movi_id', string="Pasajeros",
                                 copy=True, auto_join=True)
    movi_cost_line = fields.One2many('step.movi.cost.line', 'movi_id', string="Líneas de costeo",
                                      copy=False, auto_join=True)
    movi_cont_line = fields.One2many('step.movi.cont.line', 'movi_id', string="Distribución contable",
                                      copy=False, auto_join=True)
    passenger_event_ids = fields.One2many('step.mobilization.passenger.event', 'trip_id',
                                           string='Eventos de marcación (app móvil)', copy=False)
    gps_point_ids = fields.One2many('step.mobilization.gps.point', 'trip_id',
                                     string='Puntos GPS', copy=False)
    last_gps_at = fields.Datetime(string='Último GPS', compute='_compute_last_gps')
    last_latitude = fields.Float(string='Última latitud', compute='_compute_last_gps', digits=(10, 7))
    last_longitude = fields.Float(string='Última longitud', compute='_compute_last_gps', digits=(10, 7))
    delay_minutes = fields.Integer(string='Atraso (min)', compute='_compute_delay_minutes', store=True)

    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('open', 'Abierto'),
            ('closed', 'Cerrado'),
            ('validated', 'Validado'),
            ('costed', 'Costeado'),
            ('accounted', 'Contabilizado'),
            ('cancelled', 'Cancelado'),
        ],
        string='Estado', required=True, tracking=True, copy=False, default='draft')
    cancel_reason = fields.Text(string='Motivo de cancelación/corrección', copy=False)
    correction_user_id = fields.Many2one('res.users', string='Responsable del cambio', copy=False)

    invoice_id = fields.Many2one('account.move', string='Asiento contable', copy=False, readonly=True)
    accounted_once = fields.Boolean(string='Ya contabilizado', copy=False, default=False, readonly=True)

    boarded_count = fields.Integer(string='Abordados', compute='_compute_passenger_counts', store=True)
    aboard_count = fields.Integer(string='A bordo', compute='_compute_passenger_counts', store=True)
    alighted_count = fields.Integer(string='Descendidos', compute='_compute_passenger_counts', store=True)
    capacity = fields.Integer(string='Capacidad sentada', related='vehicle_id.step_max_pass')
    overcapacity = fields.Boolean(string='Sobrecupo', compute='_compute_passenger_counts', store=True)

    _sql_constraints = [
        ('uuid_unique', 'unique(uuid)', 'El UUID del viaje debe ser único.'),
    ]

    @api.model
    def _selection_tz(self):
        return [(tz, tz) for tz in pytz.all_timezones]

    @api.depends('passenger_event_ids.event_type', 'passenger_event_ids.passenger_id', 'capacity')
    def _compute_passenger_counts(self):
        for record in self:
            events = record.passenger_event_ids.filtered(lambda e: e.state != 'void')
            boarded = events.filtered(lambda e: e.event_type == 'boarding').mapped('passenger_id')
            alighted = events.filtered(lambda e: e.event_type == 'alighting').mapped('passenger_id')
            record.boarded_count = len(boarded)
            record.alighted_count = len(alighted)
            record.aboard_count = len(set(boarded.ids) - set(alighted.ids))
            record.overcapacity = bool(record.capacity) and record.aboard_count > record.capacity

    @api.depends('gps_point_ids.device_datetime')
    def _compute_last_gps(self):
        for record in self:
            last = record.gps_point_ids[-1:]
            record.last_gps_at = last.device_datetime if last else False
            record.last_latitude = last.latitude if last else 0.0
            record.last_longitude = last.longitude if last else 0.0

    @api.depends('scheduled_time', 'actual_start')
    def _compute_delay_minutes(self):
        for record in self:
            if record.scheduled_time and record.actual_start:
                delta = record.actual_start - record.scheduled_time
                record.delay_minutes = int(delta.total_seconds() // 60)
            else:
                record.delay_minutes = 0

    @api.model
    def _next_sequence(self, company_id):
        """Secuencia por compañía, creada bajo demanda. La secuencia MV
        heredada de step_hr era única y global (company_id=False), lo que
        mezclaba numeración entre compañías; se reemplaza por una secuencia
        propia por compañía en vez de forzar una sola global."""
        Sequence = self.env['ir.sequence'].sudo()
        seq = Sequence.search([('code', '=', 'step_moviliza_seq'), ('company_id', '=', company_id)], limit=1)
        if not seq:
            seq = Sequence.create({
                'name': _('Movilización (%s)') % self.env['res.company'].browse(company_id).name,
                'code': 'step_moviliza_seq',
                'prefix': 'MV',
                'padding': 5,
                'company_id': company_id,
            })
        return seq.next_by_id()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('Nuevo'):
                company_id = vals.get('company_id') or self.env.company.id
                vals['name'] = self._next_sequence(company_id) or _('Nuevo')
        return super().create(vals_list)

    def unlink(self):
        if any(record.state != 'draft' for record in self):
            raise UserError(_('Sólo se puede eliminar un viaje en borrador; use cancelación para los demás.'))
        return super().unlink()

    def _check_can_open(self):
        """Bloquea la apertura si la última inspección del vehículo quedó
        rechazada, o si hay un documento bloqueante vencido/faltante para
        transportista/chofer/vehículo. No es una validez legal automática:
        sólo evita abrir viajes contra evidencia ya registrada como no apta."""
        self.ensure_one()
        Inspection = self.env['step.mobilization.inspection']
        last_inspection = Inspection.search(
            [('vehicle_id', '=', self.vehicle_id.id), ('state', '!=', 'draft')],
            order='date desc', limit=1)
        if last_inspection and last_inspection.state == 'rejected':
            raise UserError(_('El vehículo %s tiene su última inspección rechazada (%s). '
                               'No se puede abrir el viaje hasta una nueva inspección o autorización.')
                             % (self.vehicle_id.display_name, last_inspection.date))
        Document = self.env['step.mobilization.document']
        blocking_expired = Document.search([
            ('type_id.is_blocking', '=', True),
            ('review_state', '!=', 'approved'),
            '|', '|',
            ('transporter_id', '=', self.partner_id.id),
            ('chofer_id', '=', self.chofer_id.id),
            ('vehicle_id', '=', self.vehicle_id.id),
        ], limit=1)
        if blocking_expired:
            raise UserError(_('Hay un documento bloqueante sin aprobar (%s) para este viaje.')
                             % blocking_expired.type_id.name)

    def action_open(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Sólo un viaje en borrador puede abrirse.'))
            record._check_can_open()
            record.write({'state': 'open', 'actual_start': fields.Datetime.now()})

    def action_close(self):
        for record in self:
            if record.state != 'open':
                raise UserError(_('Sólo un viaje abierto puede cerrarse.'))
            record.write({'state': 'closed', 'actual_end': fields.Datetime.now()})

    def action_validate(self):
        for record in self:
            if record.state != 'closed':
                raise UserError(_('Sólo un viaje cerrado puede validarse.'))
            record.write({'state': 'validated'})

    def action_cancel(self):
        for record in self:
            if not record.cancel_reason:
                raise ValidationError(_('Debe indicar un motivo para cancelar el viaje.'))
            if record.state == 'accounted':
                raise UserError(_('Un viaje contabilizado no se cancela: use la reversa contable.'))
            record.write({'state': 'cancelled', 'correction_user_id': self.env.user.id})

    # ---- Costeo ---------------------------------------------------------
    def _get_tariff_line(self):
        """Hook de resolución de tarifa. Lanza UserError si no hay tarifa
        vigente para el recorrido/sentido, en vez de dejar caer un entero 0
        que luego revienta al leer .cobro_type (bug detectado en step_hr)."""
        self.ensure_one()
        if not self.pricelist_id:
            raise UserError(_('El viaje %s no tiene lista de tarifas asignada.') % self.name)
        candidates = self.pricelist_id.move_item.filtered(lambda line: line.recorrido_id == self.recorrido_id)
        valid = candidates.filtered(
            lambda line: (not line.date_start or line.date_start <= self.date)
            and (not line.date_end or line.date_end >= self.date))
        if not valid:
            raise UserError(_('No existe una tarifa vigente para el recorrido "%s" en la lista "%s" '
                               'con fecha %s.') % (self.recorrido_id.display_name,
                                                    self.pricelist_id.display_name, self.date))
        return valid[0]

    def _get_unique_passengers(self):
        self.ensure_one()
        return self.movi_line.mapped('employee_id')

    def _get_cost_distribution_hook(self, employee):
        """Punto de extensión para el adaptador agrícola: por defecto el
        núcleo no conoce fundo/temporada/tarja, así que no arma una
        distribución analítica automática. Devuelve None si no hay hook
        instalado; step_mobilization_agriculture lo sobreescribe."""
        self.ensure_one()
        return None

    def action_costeo(self):
        if not self.env.user.has_group('step_mobilization.group_mobilization_costing'):
            raise UserError(_('No tiene permiso para costear viajes de movilización.'))
        for record in self:
            if record.state not in ('closed', 'validated'):
                raise UserError(_('Sólo se puede costear un viaje cerrado o validado.'))
            passengers = record._get_unique_passengers()
            if not passengers:
                raise UserError(_('El viaje %s no tiene pasajeros registrados.') % record.name)
            tarifa = record._get_tariff_line()
            passenger_count = len(passengers)

            # cobro_type 'ida_vuelta' es UNA tarifa por el viaje redondo completo, no una
            # tarifa completa por cada tramo: se reparte a la mitad entre ida y vuelta para
            # no duplicar el cobro de un pasajero que marca entrada y salida en el mismo viaje.
            if tarifa.cobro_type == 'ida_vuelta':
                fare_in = fare_out = tarifa.tarifa / 2.0
            elif tarifa.cobro_type == 'ida':
                fare_in, fare_out = tarifa.tarifa, 0.0
            else:
                fare_in, fare_out = 0.0, tarifa.tarifa
            per_passenger_in = fare_in / passenger_count if passenger_count else 0.0
            per_passenger_out = fare_out / passenger_count if passenger_count else 0.0

            record.movi_cost_line.unlink()
            vals = []
            for employee in passengers:
                lines = record.movi_line.filtered(lambda l: l.employee_id == employee)
                has_in = any(l.operacion == 'in' for l in lines)
                has_out = any(l.operacion == 'out' for l in lines)
                distribution = record._get_cost_distribution_hook(employee) or {}
                vals.append((0, 0, {
                    'employee_id': employee.id,
                    'recorrido_ent': record.recorrido_id.desde if has_in else False,
                    'recorrido_sal': record.recorrido_id.hasta if has_out else False,
                    'cost_in': per_passenger_in if has_in else 0.0,
                    'cost_out': per_passenger_out if has_out else 0.0,
                    'cost_total': (per_passenger_in if has_in else 0.0) + (per_passenger_out if has_out else 0.0),
                    'cost_id': distribution.get('cost_id'),
                    'labor_id': distribution.get('labor_id'),
                }))
            record.movi_cost_line = vals
            record.write({'state': 'costed'})

    def action_to_costeo(self):
        for record in self:
            record.movi_cost_line.unlink()
            record.write({'state': 'validated'})

    # ---- Contabilización --------------------------------------------------
    def action_conta(self):
        if not self.env.user.has_group('step_mobilization.group_mobilization_accounting'):
            raise UserError(_('No tiene permiso para contabilizar viajes de movilización.'))
        for movi in self:
            if movi.state != 'costed':
                raise UserError(_('Sólo se puede contabilizar un viaje costeado.'))
            if movi.accounted_once or movi.invoice_id:
                raise UserError(_('El viaje %s ya fue contabilizado.') % movi.name)
            journal = movi.company_id.step_movi_journal_id
            if not journal:
                raise UserError(_('Configure el diario contable de Movilización en Ajustes.'))
            if not journal.default_account_id:
                raise UserError(_('El diario "%s" no tiene cuenta por defecto configurada.') % journal.name)
            if not journal.account_control_ids:
                raise UserError(_('El diario "%s" no tiene cuentas de control configuradas.') % journal.name)

            move_vals = {
                'ref': movi.name,
                'date': movi.date,
                'move_type': 'entry',
                'moviliza': True,
                'journal_id': journal.id,
                'partner_id': movi.partner_id.id,
            }
            if journal.company_id.account_fiscal_country_id.code == 'CL' and movi.company_id.step_movi_document_type_id:
                move_vals['l10n_latam_document_type_id'] = movi.company_id.step_movi_document_type_id.id

            invoice = self.env['account.move'].create([move_vals])
            line_vals = []
            total = 0.0
            for line in movi.movi_cost_line:
                distribution = line._get_analytic_distribution()
                line_vals.append({
                    'name': _('Ref: %s') % movi.name,
                    'account_id': journal.default_account_id.id,
                    'debit': round(line.cost_total, 2),
                    'credit': 0.0,
                    'analytic_distribution': distribution,
                    'move_id': invoice.id,
                    'tax_ids': False,
                })
                total += line.cost_total
            line_vals.append({
                'name': _('Ref: %s') % movi.name,
                'account_id': journal.account_control_ids[0].id,
                'debit': 0.0,
                'credit': round(total, 2),
                'move_id': invoice.id,
                'tax_ids': False,
            })
            self.env['account.move.line'].create(line_vals)
            movi.write({'invoice_id': invoice.id, 'accounted_once': True, 'state': 'accounted'})

    @api.model
    def get_dashboard_data(self):
        """KPIs de la portada de Movilización. Multiempresa por construcción:
        cada búsqueda ya pasa por las ir.rule; no se agregan sin filtrar."""
        today = fields.Date.context_today(self)
        trips = self.search([])
        open_trips = trips.filtered(lambda t: t.state == 'open')
        Contract = self.env['step.mobilization.contract']
        Document = self.env['step.mobilization.document']
        Inspection = self.env['step.mobilization.inspection']
        Event = self.env['step.mobilization.passenger.event']
        return {
            'trips_open': len(open_trips),
            'trips_closed': len(trips.filtered(lambda t: t.state in ('closed', 'validated'))),
            'vehicles_active': len(open_trips.mapped('vehicle_id')),
            'passengers_aboard_now': sum(open_trips.mapped('aboard_count')),
            'passengers_transported_today': len(
                trips.filtered(lambda t: t.date == today).mapped('movi_line').mapped('employee_id')),
            'overcapacity_trips': len(trips.filtered('overcapacity')),
            'contracts_expiring_30d': Contract.search_count([
                ('state', '=', 'active'),
                ('date_end', '<=', fields.Date.add(today, days=30)),
                ('date_end', '>=', today),
            ]),
            'documents_expired': Document.search_count([
                ('expiry_date', '<', today), ('review_state', '!=', 'approved'),
            ]),
            'inspections_rejected': Inspection.search_count([('state', '=', 'rejected')]),
            'cost_this_month': sum(trips.filtered(
                lambda t: t.state in ('costed', 'accounted') and t.date
                and t.date.month == today.month and t.date.year == today.year
            ).mapped('movi_cost_line').mapped('cost_total')),
            'sync_conflicts': Event.search_count([('sync_state', '=', 'conflict')]),
        }
