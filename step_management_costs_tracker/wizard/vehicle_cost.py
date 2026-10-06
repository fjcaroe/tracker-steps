import calendar

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class StepTrackerCostWizard(models.TransientModel):
    _name = 'step.tracker.cost.wizard'
    _description = 'Costos y cantidades operativas (Tracker)'

    scope = fields.Selection([('vehicle', 'Vehículo'), ('center', 'Centro de Gestión y Costos')], required=True, default='vehicle')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', domain="[('company_id', 'in', [False, company_id])]")
    center_id = fields.Many2one('account.analytic.account', string='Centro de costo', check_company=True,
                              domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    hourly_metric = fields.Selection(
        [('session', 'Horas de sesión'), ('hourmeter', 'Horas de horómetro')], string='Costo por hora según',
        default='session', required=True,
        help='Un costo por hora siempre indica su base: el reloj de la sesión no equivale a horas de motor.')
    refresh_tracker = fields.Boolean(string='Consultar Tracker antes de calcular', default=False)
    state = fields.Selection([('setup', 'Parámetros'), ('result', 'Resultado')], default='setup')
    message = fields.Text(string='Avisos', readonly=True)
    line_ids = fields.One2many('step.tracker.cost.wizard.line', 'wizard_id', string='Resultado')

    # ------------------------------------------------------------------
    @api.model
    def action_open(self, scope, vehicle=None, center=None):
        today = fields.Date.context_today(self)
        first = today.replace(day=1)
        last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        wizard = self.create({
            'scope': scope, 'vehicle_id': vehicle.id if vehicle else False, 'center_id': center.id if center else False,
            'company_id': (vehicle or center).company_id.id or self.env.company.id, 'date_from': first, 'date_to': last})
        return {'type': 'ir.actions.act_window', 'name': _('Costos Tracker'), 'res_model': self._name,
                'res_id': wizard.id, 'view_mode': 'form', 'target': 'new'}

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'new'}

    def action_back(self):
        self.ensure_one()
        self.line_ids.unlink()
        self.state = 'setup'
        return self._reopen()

    # ------------------------------------------------------------------
    def action_compute(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(_('La fecha «hasta» no puede ser anterior a «desde».'))
        if self.scope == 'vehicle' and not self.vehicle_id or self.scope == 'center' and not self.center_id:
            raise UserError(_('Seleccione el vehículo o el centro.'))
        notes = []
        if self.refresh_tracker and self.scope == 'vehicle':
            try:
                utc_from, utc_to = self.env['step.tracker.vehicle.cost']._bounds(self.company_id, self.date_from, self.date_to)
                outcome = self.env['step.tracker.usage.sync'].sudo().with_company(self.company_id).sync_period(
                    self.company_id, utc_from, utc_to)
                notes += outcome['warnings']
                notes.append(_('Consulta a Tracker completa (%s sesiones).') % outcome['fetched'] if outcome['complete']
                             else _('La consulta a Tracker no se pudo dar por completa.'))
            except UserError as exc:
                notes.append(_('Se calculó con los datos ya cargados: %s') % exc.args[0])
        service = self.env['step.tracker.vehicle.cost']
        result = service.compute(
            vehicle=self.vehicle_id if self.scope == 'vehicle' else None,
            center=self.center_id if self.scope == 'center' else None,
            date_from=self.date_from, date_to=self.date_to, hourly_metric=self.hourly_metric, company=self.company_id)
        self.line_ids.unlink()
        self.env['step.tracker.cost.wizard.line'].create(self._lines(result))
        self.write({'state': 'result', 'message': '\n'.join(notes) or False})
        return self._reopen()

    # ------------------------------------------------------------------
    def _fmt_money(self, value, currency):
        return formatLang(self.env, value, currency_obj=currency) if value is not None else _('No disponible')

    def _lines(self, result):
        self.ensure_one()
        currency = self.company_id.currency_id
        money = lambda v: self._fmt_money(v, currency)
        number = lambda v, unit, digits=2: '%s %s' % (formatLang(self.env, v, digits=digits), unit)
        rows = []

        def add(section, label, value, status='ok', note=''):
            rows.append({'wizard_id': self.id, 'sequence': len(rows), 'section': section, 'label': label,
                         'value': value, 'status': status, 'note': note or False})

        access = result['access']
        if not any(access.values()):
            add(_('Acceso'), _('Datos financieros'), _('Sin acceso'), 'unavailable',
                _('Su usuario no tiene permisos de Gastos, contabilidad ni Gestión y Costos.'))
        real, pending = result['real'], result['pending']
        add(_('Costo real'), _('Costo real contabilizado'),
            money(real['amount']) if real['available'] else _('No disponible'),
            'ok' if real['available'] else 'unavailable', real.get('basis') or real.get('reason', ''))
        if real.get('missing_rates'):
            add(_('Costo real'), _('Monedas sin tipo de cambio'), ', '.join(real['missing_rates']), 'incomplete')
        for item in real.get('by_currency', []):
            add(_('Costo real'), _('Origen en %s (informativo, no se suma)') % item['currency'], '%s' % item['amount'], 'info')
        add(_('Gasto pendiente'), _('Pendiente de contabilizar (borrador, informado, aprobado)'),
            money(pending.get('amount')) if pending['available'] else _('No disponible'),
            'info' if pending['available'] else 'unavailable',
            _('Se muestra aparte: no forma parte del costo real.'))
        for state in pending.get('by_state', []):
            add(_('Gasto pendiente'), '%s (%s)' % (state['label'], state['count']), money(state['amount']), 'info')
        if result['scope'] == 'vehicle':
            unattributed = result['unattributed']
            if unattributed['available']:
                add(_('Gasto pendiente'), _('Gastos de rendiciones con uso de este vehículo sin vehículo asignado'),
                    '%s · %s' % (unattributed['count'], money(unattributed['amount'])),
                    'incomplete' if unattributed['count'] else 'info',
                    _('No atribuidos: no se reparten entre vehículos sin una regla explícita.'))
            by_center = result['by_center']
            for row in by_center.get('rows', []):
                add(_('Por centro / cuenta analítica'), '%s · %s' % (row['plan'], row['account']), money(row['amount']), 'info',
                    _('Centro: %s') % row['center'] if row['center'] else (
                        _('Varias fichas usan esta cuenta') if row['shared_account'] else ''))
            if by_center.get('unassigned'):
                add(_('Por centro / cuenta analítica'), _('Sin distribución analítica'), money(by_center['unassigned']), 'info')
        quantities = result.get('quantities')
        if quantities:
            add(_('Cantidades operativas'), _('Distancia GPS válida'), number(quantities['km']['value'], 'km', 3), 'ok',
                _('%s sesión(es) cerrada(s) con distancia.') % quantities['km']['sessions'])
            add(_('Cantidades operativas'), _('Horas de sesión'), number(quantities['session_hours']['value'], 'h'), 'ok',
                _('Reloj de la sesión; no son horas de motor.'))
            hourmeter = quantities['hourmeter_hours']
            add(_('Cantidades operativas'), _('Horas de horómetro (partes)'), number(hourmeter['value'], 'h'),
                'ok' if hourmeter['work_orders'] else 'unavailable',
                _('%(w)s parte(s) con lectura; %(s)s sesión(es) sin lectura.') % {
                    'w': hourmeter['work_orders'], 's': hourmeter['sessions_without_reading']})
            excluded = quantities['excluded']
            if excluded['open'] or excluded['closed_without_distance']:
                add(_('Cantidades operativas'), _('Sesiones excluidas'),
                    _('%(o)s abierta(s) · %(d)s sin distancia') % {'o': excluded['open'], 'd': excluded['closed_without_distance']},
                    'incomplete')
            add(_('Cantidades operativas'), _('Última sincronización de sesiones'), quantities['last_sync'] or _('Sin sesiones'),
                'info', quantities['coverage_note'])
        for key in ('cost_per_km', 'cost_per_hour'):
            indicator = result.get('indicators', {}).get(key)
            if not indicator:
                continue
            if indicator['status'] == 'ok':
                add(_('Indicadores'), indicator['label'], '%s / %s' % (money(indicator['value']), indicator['unit']), 'ok')
            else:
                text = _('No disponible / información incompleta')
                if indicator['partial'] is not None:
                    text += _(' (valor parcial de referencia: %s / %s)') % (money(indicator['partial']), indicator['unit'])
                add(_('Indicadores'), indicator['label'], text, indicator['status'], ' '.join(indicator['reasons']))
        if result['scope'] == 'center':
            budget = result['budget']
            if budget['available']:
                add(_('Presupuesto'), _('Presupuesto aprobado del período'), money(budget['amount']), 'ok', ', '.join(budget['budgets']))
                if budget['variance'] is not None:
                    add(_('Presupuesto'), _('Desviación (real − presupuesto)'), money(budget['variance']), 'ok',
                        _('%s %%') % budget['variance_percent'] if budget['variance_percent'] is not None else '')
                if budget['reason']:
                    add(_('Presupuesto'), _('Aviso'), budget['reason'], 'incomplete')
            else:
                add(_('Presupuesto'), _('Presupuesto del período'), _('No disponible'), 'unavailable', budget['reason'])
            if result.get('shared_account'):
                add(_('Avisos'), _('Cuenta analítica compartida'), ', '.join(result['shared_account']), 'incomplete',
                    _('El importe es el de la cuenta completa; no se reparte entre fichas.'))
        return rows


class StepTrackerCostWizardLine(models.TransientModel):
    _name = 'step.tracker.cost.wizard.line'
    _description = 'Línea de resultado de costos Tracker'
    _order = 'sequence, id'

    wizard_id = fields.Many2one('step.tracker.cost.wizard', required=True, ondelete='cascade')
    sequence = fields.Integer()
    section = fields.Char(string='Sección')
    label = fields.Char(string='Concepto')
    value = fields.Char(string='Valor')
    status = fields.Selection([('ok', 'Completo'), ('info', 'Informativo'), ('incomplete', 'Información incompleta'),
                               ('unavailable', 'No disponible')], string='Estado')
    note = fields.Text(string='Base / observación')
