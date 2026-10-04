from datetime import datetime, time, timedelta, timezone

from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..models.expense_vehicle_line import IMPORT_CONTEXT

MAX_PERIOD_DAYS = 100


class StepExpenseTrackerImport(models.TransientModel):
    """Buscar y previsualizar NO crea gastos: solo «Incorporar» escribe líneas de uso en borrador."""
    _name = 'step.expense.tracker.import'
    _description = 'Traer recorridos desde Tracker a una rendición'

    sheet_id = fields.Many2one('hr.expense.sheet', string='Rendición', required=True, readonly=True, ondelete='cascade')
    company_id = fields.Many2one(related='sheet_id.company_id')
    sheet_employee_id = fields.Many2one(related='sheet_id.employee_id')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True,
                                 domain="[('company_id', 'in', [False, company_id])]")
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    zone_name = fields.Char(string='Zona horaria de la operación', compute='_compute_zone_name')
    use_tracker_sync = fields.Boolean(string='Consultar Tracker ahora', default=True,
                                      help='Trae de Tracker las sesiones del período antes de listarlas. '
                                           'Desactívelo para trabajar solo con lo ya cargado en Odoo.')
    allow_reuse = fields.Boolean(string='Permitir sesiones ya usadas en otra rendición')
    state = fields.Selection([('setup', 'Parámetros'), ('preview', 'Vista previa')], default='setup')
    line_ids = fields.One2many('step.expense.tracker.import.line', 'wizard_id', string='Recorridos')
    coverage_complete = fields.Boolean(readonly=True)
    coverage_message = fields.Text(string='Cobertura de la consulta', readonly=True)
    unmapped_count = fields.Integer(string='Sesiones sin vehículo Odoo', readonly=True)
    selected_count = fields.Integer(compute='_compute_selected')
    selected_km = fields.Float(compute='_compute_selected', digits=(16, 3))

    # ------------------------------------------------------------------
    @api.model
    def default_get(self, field_names):
        values = super().default_get(field_names)
        sheet = self.env['hr.expense.sheet'].browse(values.get('sheet_id') or self.env.context.get('default_sheet_id'))
        if sheet:
            vehicle = (sheet.vehicle_line_ids.filtered('vehicle_id')[-1:].vehicle_id
                       or sheet.expense_line_ids.step_vehicle_id[:1])
            dates = [d for d in sheet.expense_line_ids.mapped('date') if d]
            today = fields.Date.context_today(self)
            values.update({
                'sheet_id': sheet.id,
                'vehicle_id': vehicle.id if vehicle else False,
                'date_from': min(dates) if dates else today - timedelta(days=30),
                'date_to': max(dates) if dates else today,
            })
        return values

    @api.depends('company_id')
    def _compute_zone_name(self):
        for wizard in self:
            wizard.zone_name = str(wizard.company_id._step_operation_zone()) if wizard.company_id else ''

    @api.depends('line_ids.selected', 'line_ids.distance_km')
    def _compute_selected(self):
        for wizard in self:
            chosen = wizard.line_ids.filtered('selected')
            wizard.selected_count = len(chosen)
            wizard.selected_km = sum(chosen.mapped('distance_km'))

    # ------------------------------------------------------------------
    # Período en hora local -> UTC
    # ------------------------------------------------------------------
    def _period_utc(self):
        """[00:00 de «desde», 00:00 del día siguiente a «hasta») en la zona de la operación, como UTC naive.
        El cambio de hora no rompe los límites: zoneinfo resuelve una medianoche inexistente al instante
        real de la transición."""
        self.ensure_one()
        zone = self.company_id._step_operation_zone()

        def to_utc(day):
            return datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)

        return to_utc(self.date_from), to_utc(self.date_to + timedelta(days=1))

    @api.model
    def _local(self, company, value):
        """datetime UTC naive -> datetime local de la operación."""
        return value.replace(tzinfo=timezone.utc).astimezone(company._step_operation_zone()) if value else False

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    def _check_inputs(self):
        self.ensure_one()
        sheet = self.sheet_id
        if sheet.state != 'draft':
            raise UserError(_('Solo se pueden traer recorridos a una rendición en borrador.'))
        if self.date_to < self.date_from:
            raise UserError(_('La fecha «hasta» no puede ser anterior a «desde».'))
        if (self.date_to - self.date_from).days > MAX_PERIOD_DAYS:
            raise UserError(_('El período no puede superar %s días.') % MAX_PERIOD_DAYS)
        vehicle = self.vehicle_id
        if vehicle.company_id and vehicle.company_id != sheet.company_id:
            raise UserError(_('El vehículo %s pertenece a otra empresa que la rendición.') % vehicle.display_name)

    # ------------------------------------------------------------------
    # Vista previa
    # ------------------------------------------------------------------
    def action_preview(self):
        self.ensure_one()
        self._check_inputs()
        company = self.company_id
        date_from, date_to = self._period_utc()
        messages = []
        complete = False
        configured = bool(company.sudo().step_tracker_base_url)
        if self.use_tracker_sync and configured:
            machines = self.env['step.tracker.machine'].sudo().search([
                ('vehicle_id', '=', self.vehicle_id.id), ('company_id', '=', company.id)])
            result = self.env['step.tracker.usage.sync'].sudo().with_company(company).sync_period(
                company, date_from, date_to,
                machine_tracker_id=machines.tracker_id if len(machines) == 1 else None)
            complete = result['complete']
            messages += result['warnings']
            if complete:
                messages.append(_('Período consultado completo en Tracker (%s sesiones recibidas).') % result['fetched'])
        else:
            messages.append(_(
                'No se consultó Tracker: se muestran solo los recorridos ya cargados en Odoo y pueden faltar '
                'sesiones del período.'))

        Usage = self.env['step.tracker.usage']
        base_domain = Usage._period_domain(date_from, date_to) + [('company_id', '=', company.id)]
        usages = Usage.search(base_domain + [('vehicle_id', '=', self.vehicle_id.id)], order='started_at asc, id asc')
        unmapped = Usage.search_count(base_domain + [('vehicle_id', '=', False)])
        if unmapped:
            messages.append(_(
                '%s sesión(es) del período no están asociadas a ningún vehículo de Odoo (máquina de Tracker sin '
                'vínculo); no se pueden atribuir a este vehículo.') % unmapped)
        if not usages:
            messages.append(_('No hay recorridos de este vehículo en el período.'))

        used_elsewhere = {}
        if usages:
            others = self.env['step.expense.vehicle.line'].sudo().search([
                ('usage_id', 'in', usages.ids), ('sheet_id', '!=', self.sheet_id.id), ('sheet_id.state', '!=', 'cancel')])
            for line in others:
                used_elsewhere.setdefault(line.usage_id.id, []).append(line.sheet_id.folio or line.sheet_id.display_name)
        in_sheet = self.sheet_id.vehicle_line_ids.usage_id

        self.line_ids.unlink()
        Line = self.env['step.expense.tracker.import.line']
        Line.create([
            self._preview_line_values(usage, date_from, date_to, used_elsewhere.get(usage.id, []), in_sheet)
            for usage in usages
        ])
        self.write({'state': 'preview', 'coverage_complete': complete, 'coverage_message': '\n'.join(messages),
                    'unmapped_count': unmapped})
        return self._reopen()

    def _preview_line_values(self, usage, date_from, date_to, used_in, in_sheet):
        self.ensure_one()
        company = self.company_id
        local_start = self._local(company, usage.started_at)
        local_end = self._local(company, usage.ended_at)
        issues = list(usage._data_issues())
        crosses_start = usage.started_at < date_from
        crosses_end = not usage.ended_at or usage.ended_at >= date_to
        if crosses_start:
            issues.append(_('Empieza antes del período (se asigna completo a su fecha de inicio)'))
        if crosses_end and usage.ended_at:
            issues.append(_('Termina después del período (se asigna completo a su fecha de inicio)'))
        if local_end and local_start.date() != local_end.date():
            issues.append(_('Cruza la medianoche'))
        if not usage.driver_id:
            issues.append(_('Conductor no identificado en la sesión'))
        elif not usage.employee_id:
            issues.append(_('Conductor sin empleado Odoo asociado'))
        elif usage.employee_id != self.sheet_employee_id:
            issues.append(_('Conductor distinto del empleado de la rendición (%s)') % usage.employee_id.name)
        if not usage.analytic_account_id:
            issues.append(_('Sin cuenta analítica para el centro de costo'))
        shared = usage.work_order_session_count > 1
        if shared and (usage.hourmeter_known or usage.fuel_refill_known):
            issues.append(_('El parte %(code)s cubre %(count)s sesiones: su horómetro y su recarga no se asignan a una sola') % {
                'code': usage.work_order_code or usage.work_order_tracker_id, 'count': usage.work_order_session_count})
        already = usage in in_sheet
        if already:
            issues.append(_('Ya está en esta rendición'))
        if used_in:
            issues.append(_('Ya utilizada en: %s') % ', '.join(sorted(set(used_in))))
        selectable = bool(usage.is_closed_fact) and not already and (not used_in or self.allow_reuse)
        return {
            'wizard_id': self.id, 'usage_id': usage.id,
            'selectable': selectable,
            'selected': selectable and not crosses_start and not crosses_end and usage.distance_known,
            'local_date': local_start.date(), 'started_at': usage.started_at, 'ended_at': usage.ended_at,
            'duration_hours': usage.duration_hours, 'distance_km': usage.distance_km,
            'distance_known': usage.distance_known, 'employee_id': usage.employee_id.id,
            'analytic_account_id': usage.analytic_account_id.id,
            'hourmeter_available': usage.hourmeter_known and not shared,
            'hourmeter_initial': usage.hourmeter_initial, 'hourmeter_final': usage.hourmeter_final,
            'refill_available': usage.fuel_refill_known and usage.fuel_refill_liters > 0 and not shared,
            'refill_liters': usage.fuel_refill_liters,
            'estimated_fuel_liters': usage.estimated_fuel_liters,
            'work_order_code': usage.work_order_code, 'used_in': ', '.join(sorted(set(used_in))),
            'issues': '; '.join(issues),
        }

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'new',
        }

    def action_back(self):
        self.ensure_one()
        self.line_ids.unlink()
        self.state = 'setup'
        return self._reopen()

    # ------------------------------------------------------------------
    # Valores de la línea de rendición (también los usa la actualización explícita)
    # ------------------------------------------------------------------
    @api.model
    def _line_values_from_usage(self, usage, use_refill=False):
        usage.ensure_one()
        company = usage.company_id
        local_start = self._local(company, usage.started_at)
        local_end = self._local(company, usage.ended_at)
        shared = usage.work_order_session_count > 1
        has_hourmeter = usage.hourmeter_known and not shared
        refill = usage.fuel_refill_liters if (
            use_refill and usage.fuel_refill_known and usage.fuel_refill_liters > 0 and not shared) else 0.0
        machine = usage.machine_id.name or ''
        route = _('Recorrido GPS %(machine)s · %(start)s–%(end)s · sesión %(uuid)s') % {
            'machine': machine, 'start': local_start.strftime('%H:%M'),
            'end': local_end.strftime('%H:%M') if local_end else '?', 'uuid': usage.session_uuid[:8]}
        return {
            'date': local_start.date(), 'route': route,
            'start_reading': usage.hourmeter_initial if has_hourmeter else 0.0,
            'end_reading': usage.hourmeter_final if has_hourmeter else 0.0,
            'distance': round(usage.distance_km, 3), 'liters': refill,
            'vehicle_id': usage.vehicle_id.id, 'driver_employee_id': usage.employee_id.id,
            'usage_id': usage.id, 'source': 'tracker',
            'imported_at': fields.Datetime.now(), 'imported_by_id': usage.env.uid,
            'analytic_account_id': usage.analytic_account_id.id,
            'liters_source': 'work_order_refill' if refill else 'manual',
            'src_date': local_start.date(), 'src_distance_km': round(usage.distance_km, 3),
            'src_distance_known': usage.distance_known, 'src_started_at': usage.started_at,
            'src_ended_at': usage.ended_at, 'src_duration_hours': usage.duration_hours,
            'src_hourmeter_initial': usage.hourmeter_initial if has_hourmeter else 0.0,
            'src_hourmeter_final': usage.hourmeter_final if has_hourmeter else 0.0,
            'src_hourmeter_known': has_hourmeter, 'src_liters': refill,
            'src_estimated_fuel_liters': usage.estimated_fuel_liters, 'src_work_order_code': usage.work_order_code,
        }

    # ------------------------------------------------------------------
    # Confirmación: idempotente y segura ante concurrencia
    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        sheet = self.sheet_id
        # Serializa confirmaciones simultáneas sobre la misma rendición; la restricción única
        # (sheet_id, usage_id) es la garantía final aunque el bloqueo no alcance.
        self.env.cr.execute('SELECT id FROM hr_expense_sheet WHERE id = %s FOR UPDATE', [sheet.id])
        sheet.invalidate_recordset(['state', 'vehicle_line_ids'])
        self._check_inputs()
        chosen = self.line_ids.filtered('selected')
        if not chosen:
            raise UserError(_('Seleccione al menos un recorrido.'))
        Line = self.env['step.expense.vehicle.line'].with_context(**{IMPORT_CONTEXT: True})
        existing = sheet.vehicle_line_ids.usage_id
        created = skipped = 0
        for wizard_line in chosen:
            usage = wizard_line.usage_id
            if usage in existing:
                skipped += 1
                continue
            self._assert_usage_importable(usage, wizard_line)
            values = self._line_values_from_usage(usage, use_refill=wizard_line.use_refill and wizard_line.refill_available)
            values['sheet_id'] = sheet.id
            try:
                with self.env.cr.savepoint():
                    Line.create(values)
                created += 1
            except (IntegrityError, ValidationError):
                # Otra confirmación ganó la carrera: la línea ya existe, no se duplica.
                skipped += 1
        sheet.invalidate_recordset(['vehicle_line_ids'])
        if created:
            sheet.use_vehicle = True
            sheet._step_tracker_log(_(
                'Se incorporaron %(created)s recorrido(s) desde Tracker (vehículo %(vehicle)s, %(start)s a %(end)s).'
            ) % {'created': created, 'vehicle': self.vehicle_id.display_name, 'start': self.date_from, 'end': self.date_to})
        message = _('%(created)s recorrido(s) incorporado(s); %(skipped)s ya estaban en la rendición.') % {
            'created': created, 'skipped': skipped}
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Tracker'), 'message': message, 'type': 'success', 'sticky': False,
                       'next': {'type': 'ir.actions.act_window_close'}},
        }

    def _assert_usage_importable(self, usage, wizard_line):
        self.ensure_one()
        usage = usage.sudo()
        if not usage.is_closed_fact:
            raise UserError(_('La sesión %s está abierta o incompleta y no se puede incorporar.') % usage.session_uuid[:8])
        if usage.vehicle_id != self.vehicle_id or usage.company_id != self.company_id:
            raise UserError(_('La sesión %s no corresponde al vehículo o a la empresa de la rendición.') % usage.session_uuid[:8])
        if not self.allow_reuse:
            taken = self.env['step.expense.vehicle.line'].sudo().search([
                ('usage_id', '=', usage.id), ('sheet_id', '!=', self.sheet_id.id), ('sheet_id.state', '!=', 'cancel')], limit=1)
            if taken:
                raise UserError(_('La sesión %(uuid)s ya fue utilizada en la rendición %(folio)s.') % {
                    'uuid': usage.session_uuid[:8], 'folio': taken.sheet_id.folio or taken.sheet_id.display_name})


class StepExpenseTrackerImportLine(models.TransientModel):
    _name = 'step.expense.tracker.import.line'
    _description = 'Recorrido de Tracker en la vista previa de importación'
    _order = 'started_at, id'

    wizard_id = fields.Many2one('step.expense.tracker.import', required=True, ondelete='cascade')
    usage_id = fields.Many2one('step.tracker.usage', string='Sesión', required=True, readonly=True)
    selected = fields.Boolean(string='Incorporar')
    selectable = fields.Boolean(readonly=True)
    use_refill = fields.Boolean(string='Usar recarga del parte')
    refill_available = fields.Boolean(readonly=True)
    hourmeter_available = fields.Boolean(readonly=True)
    local_date = fields.Date(string='Fecha', readonly=True)
    started_at = fields.Datetime(string='Inicio', readonly=True)
    ended_at = fields.Datetime(string='Término', readonly=True)
    duration_hours = fields.Float(string='Duración (h)', readonly=True)
    distance_km = fields.Float(string='Km GPS', digits=(16, 3), readonly=True)
    distance_known = fields.Boolean(readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Conductor', readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Centro de costo', readonly=True)
    hourmeter_initial = fields.Float(string='Horómetro inicial', digits=(16, 2), readonly=True)
    hourmeter_final = fields.Float(string='Horómetro final', digits=(16, 2), readonly=True)
    refill_liters = fields.Float(string='Recarga del parte (L)', digits=(16, 2), readonly=True)
    estimated_fuel_liters = fields.Float(string='Estimado (no cuenta)', digits=(16, 2), readonly=True)
    work_order_code = fields.Char(string='Parte', readonly=True)
    used_in = fields.Char(string='Usada en', readonly=True)
    issues = fields.Text(string='Observaciones', readonly=True)
