"""Costos, cantidades operativas e indicadores por vehículo y por centro.

Circuito (una sola vez cada importe):

    rendición (hr.expense.sheet) → asiento publicado (account.move) → distribución analítica
    → costo real de Gestión y Costos

* **Costo real** = apuntes publicados (``parent_state = 'posted'``) de cuentas de gasto. Es la misma
  fuente que ``step_management_costs`` (``analytic_actuals``). Las rendiciones NO se suman aparte: por eso
  una factura reflejada en una rendición y en la contabilidad cuenta una sola vez.
* **Gasto pendiente** = gastos en borrador / informados / aprobados que aún no tienen asiento publicado.
  Se muestra separado y nunca forma parte del costo real.
* **Cantidad operativa** = hechos de uso de Tracker (``step.tracker.usage``), asignados a su fecha local de
  inicio: cada sesión cae en un único período, de modo que períodos contiguos no duplican kilómetros.
* **Presupuesto** = meses aprobados/cerrados del presupuesto del centro; solo se compara con períodos de
  meses completos y en la misma moneda.

No se escribe nada (ni en ``step.management.historical.cost`` ni en la contabilidad) y no se usa ``sudo``
sobre gastos o asientos: lo que el usuario no puede leer se informa como no disponible.
"""
from datetime import datetime, time, timedelta, timezone

from odoo import _, api, fields, models
from odoo.tools import float_compare

# El estado de un gasto NO basta: en Odoo 18 «approved» incluye rendiciones ya contabilizadas y sin pagar.
# Pendiente = sin rendición o con rendición sin asientos publicados (borrador, enviada, aprobada).
PENDING_SHEET_STATES = ('draft', 'submit', 'approve')
PENDING_STATES = ('draft', 'reported', 'submitted', 'approved')
STATE_LABELS = {'draft': 'Borrador', 'reported': 'Informado', 'submitted': 'Enviado',
                'approved': 'Aprobado', 'done': 'Contabilizado', 'refused': 'Rechazado'}
MAX_DOCUMENTS = 200


class StepTrackerVehicleCost(models.AbstractModel):
    _name = 'step.tracker.vehicle.cost'
    _description = 'Costos por vehículo y centro a partir de Tracker'

    # ------------------------------------------------------------------
    # Período en hora local -> UTC
    # ------------------------------------------------------------------
    @api.model
    def _bounds(self, company, date_from, date_to):
        zone = company._step_operation_zone()

        def to_utc(day):
            return datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)

        return to_utc(date_from), to_utc(date_to + timedelta(days=1))

    @api.model
    def _money(self, company, amount):
        return company.currency_id.round(amount)

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------
    @api.model
    def compute(self, vehicle=None, center=None, date_from=None, date_to=None, hourly_metric='session', company=None):
        if bool(vehicle) == bool(center):
            raise ValueError('Indique un vehículo o un centro, no ambos.')
        company = company or (vehicle or center).company_id or self.env.company
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        currency = company.currency_id
        result = {
            'scope': 'vehicle' if vehicle else 'center',
            'company': {'id': company.id, 'name': company.name},
            'currency': {'name': currency.name, 'symbol': currency.symbol, 'decimals': currency.decimal_places},
            'period': {'from': fields.Date.to_string(date_from), 'to': fields.Date.to_string(date_to),
                       'zone': str(company._step_operation_zone())},
            'access': self._access(),
            'hourly_metric': hourly_metric,
        }
        if vehicle:
            result['vehicle'] = {'id': vehicle.id, 'name': vehicle.display_name, 'plate': vehicle.license_plate or ''}
            self._vehicle_sections(result, company, vehicle, date_from, date_to, hourly_metric)
        else:
            result['center'] = {'id': center.id, 'name': center.display_name, 'code': center.code,
                                'analytic_account': center.analytic_account_id.display_name or ''}
            self._center_sections(result, company, center, date_from, date_to)
        return result

    @api.model
    def _access(self):
        # «Gastos» aquí significa ver los gastos de TODOS (aprobador total o administrador): un empleado ve solo los
        # suyos y un equipo solo los de su equipo, y con eso no se puede presentar el total de un vehículo. Igual con
        # la contabilidad: los aprobadores de gastos tienen lectura parcial de apuntes; solo el perfil contable de
        # consulta (o superior) ve todo. Lo que el perfil no cubre se informa como no disponible (sin sudo).
        return {
            'expenses': self.env.user.has_group('hr_expense.group_hr_expense_user') and self.env['hr.expense'].has_access('read'),
            'accounting': self.env.user.has_group('account.group_account_readonly') and self.env['account.move.line'].has_access('read'),
            'management': self.env['step.management.cost.center'].has_access('read'),
        }

    # ------------------------------------------------------------------
    # Cantidades operativas (hechos de uso)
    # ------------------------------------------------------------------
    @api.model
    def _quantities(self, company, domain_extra, date_from, date_to):
        utc_from, utc_to = self._bounds(company, date_from, date_to)
        Usage = self.env['step.tracker.usage']
        domain = [('company_id', '=', company.id), ('started_at', '>=', utc_from), ('started_at', '<', utc_to)] + domain_extra
        sessions = Usage.search(domain)
        closed = sessions.filtered('is_closed_fact')
        with_distance = closed.filtered('distance_known')
        no_distance = closed - with_distance
        open_sessions = sessions - closed
        # El parte diario cubre una jornada, no una sesión: cada parte cuenta una sola vez.
        readings, seen = 0.0, set()
        for usage in closed.filtered('hourmeter_known'):
            if usage.work_order_tracker_id in seen:
                continue
            seen.add(usage.work_order_tracker_id)
            readings += usage.hourmeter_final - usage.hourmeter_initial
        without_hourmeter = closed.filtered(lambda u: not u.hourmeter_known)
        last_sync = max([s for s in sessions.mapped('synced_at') if s], default=False)
        return {
            'sessions': len(sessions),
            'km': {'label': 'Distancia GPS', 'unit': 'km', 'value': round(sum(with_distance.mapped('distance_km')), 3),
                   'sessions': len(with_distance)},
            'session_hours': {'label': 'Horas de sesión (reloj de la sesión, no horas de motor)', 'unit': 'h',
                              'value': round(sum(closed.mapped('duration_hours')), 2), 'sessions': len(closed)},
            'hourmeter_hours': {'label': 'Horas de horómetro registradas en partes', 'unit': 'h',
                                'value': round(readings, 2), 'work_orders': len(seen),
                                'sessions_without_reading': len(without_hourmeter)},
            'excluded': {'open': len(open_sessions), 'closed_without_distance': len(no_distance)},
            'last_sync': fields.Datetime.to_string(last_sync) if last_sync else None,
            'coverage_note': _('Basado en las sesiones ya sincronizadas desde Tracker; no se consultó Tracker ahora.'),
        }

    # ------------------------------------------------------------------
    # Vehículo
    # ------------------------------------------------------------------
    @api.model
    def _vehicle_sections(self, result, company, vehicle, date_from, date_to, hourly_metric):
        access = result['access']
        quantities = self._quantities(company, [('vehicle_id', '=', vehicle.id)], date_from, date_to)
        result['quantities'] = quantities

        real = {'available': False, 'amount': None, 'lines': 0, 'by_currency': [], 'reason': '',
                'basis': _('Neto: apuntes publicados de cuentas de gasto de rendiciones atribuidas explícitamente al '
                           'vehículo, con sus reversas. No incluye costeo interno de maquinaria ni gastos sin vehículo.')}
        by_center = {'rows': [], 'unassigned': 0.0, 'note': _(
            'Importes por cuenta analítica de cada plan; no se suman entre planes distintos.')}
        if access['accounting'] and access['expenses']:
            lines = self._vehicle_posted_lines(company, vehicle, date_from, date_to)
            real.update(available=True, amount=self._money(company, sum(lines.mapped('balance'))), lines=len(lines),
                        by_currency=self._by_currency(lines))
            by_center = dict(by_center, **self._distribute(company, lines))
            missing = self._missing_rates(company, lines.currency_id)
            if missing:
                real['missing_rates'] = missing
        elif access['accounting']:
            # La atribución al vehículo pasa por el gasto (hr.expense): sin verlos todos, un cero sería engañoso.
            real['reason'] = _('La atribución por vehículo necesita permiso de lectura de todos los gastos.')
        else:
            real['reason'] = _('Sin permiso de lectura contable.')
        result['real'] = real
        result['by_center'] = by_center

        pending = {'available': False, 'amount': None, 'count': 0, 'by_state': []}
        unattributed = {'available': False, 'count': 0, 'amount': 0.0}
        documents = []
        if access['expenses']:
            Expense = self.env['hr.expense']
            base = [('company_id', '=', company.id), ('step_vehicle_id', '=', vehicle.id),
                    ('date', '>=', date_from), ('date', '<=', date_to)]
            pending_expenses = self._pending_expenses(company, date_from, date_to, [('step_vehicle_id', '=', vehicle.id)])
            pending.update(available=True, amount=self._money(company, sum(pending_expenses.mapped('total_amount'))),
                           count=len(pending_expenses),
                           by_state=[{'state': state, 'label': STATE_LABELS[state], 'count': len(group),
                                      'amount': self._money(company, sum(group.mapped('total_amount')))}
                                     for state in PENDING_STATES
                                     for group in [pending_expenses.filtered(lambda e, s=state: e.state == s)] if group])
            missing = self._missing_rates(company, pending_expenses.currency_id)
            if missing:
                pending['missing_rates'] = missing
            result['pending_missing_rates'] = missing
            unassigned = self._unattributed_expenses(company, vehicle, date_from, date_to)
            unattributed.update(available=True, count=len(unassigned),
                                amount=self._money(company, sum(unassigned.mapped('total_amount'))))
            documents = self._documents(Expense.search(base + [('state', '!=', 'refused')], order='date desc, id desc',
                                                        limit=MAX_DOCUMENTS))
        result['pending'] = pending
        result['unattributed'] = unattributed
        result['documents'] = documents

        result['indicators'] = {
            'cost_per_km': self._unit_indicator(
                real, quantities, unattributed, pending=pending, label=_('Costo por km'), unit='km',
                denominator=quantities['km']['value'], denominator_sessions_missing=quantities['excluded']['closed_without_distance'],
                missing_denominator_text=_('Sin kilómetros GPS válidos en el período.'),
                partial_reasons=self._excluded_reasons(quantities)),
            'cost_per_hour': self._hour_indicator(real, quantities, unattributed, pending, hourly_metric),
        }

    @api.model
    def _pending_expenses(self, company, date_from, date_to, extra=None):
        """Gastos que todavía no son costo real: sin rendición o con una rendición sin asientos publicados. Si el
        usuario puede leer la contabilidad, además se descarta cualquier gasto que ya tenga un apunte publicado."""
        expenses = self.env['hr.expense'].search([
            ('company_id', '=', company.id), ('date', '>=', date_from), ('date', '<=', date_to),
            '|', ('sheet_id', '=', False), ('sheet_id.state', 'in', PENDING_SHEET_STATES)] + (extra or []))
        if expenses and self.env['account.move.line'].has_access('read'):
            expenses -= self.env['account.move.line'].search([
                ('parent_state', '=', 'posted'), ('expense_id', 'in', expenses.ids)]).expense_id
        return expenses

    @api.model
    def _excluded_reasons(self, quantities):
        reasons = []
        if quantities['excluded']['open']:
            reasons.append(_('%s sesión(es) abierta(s) o sin término no se cuentan.') % quantities['excluded']['open'])
        if quantities['excluded']['closed_without_distance']:
            reasons.append(_('%s sesión(es) cerrada(s) sin distancia GPS no aportan kilómetros.')
                           % quantities['excluded']['closed_without_distance'])
        return reasons

    @api.model
    def _hour_indicator(self, real, quantities, unattributed, pending, metric):
        if metric == 'hourmeter':
            hours = quantities['hourmeter_hours']
            partial = self._excluded_reasons(quantities)
            if hours['sessions_without_reading']:
                partial.append(_('%s sesión(es) cerrada(s) no tienen lectura de horómetro registrada.')
                               % hours['sessions_without_reading'])
            return self._unit_indicator(
                real, quantities, unattributed, pending=pending, label=_('Costo por hora de horómetro'), unit='h',
                denominator=hours['value'], denominator_sessions_missing=0,
                missing_denominator_text=_('Sin lecturas de horómetro registradas en partes del período.'),
                partial_reasons=partial)
        return self._unit_indicator(
            real, quantities, unattributed, pending=pending, label=_('Costo por hora de sesión'), unit='h',
            denominator=quantities['session_hours']['value'], denominator_sessions_missing=0,
            missing_denominator_text=_('Sin horas de sesión cerradas en el período.'),
            partial_reasons=self._excluded_reasons(quantities))

    @api.model
    def _unit_indicator(self, real, quantities, unattributed, pending, label, unit, denominator,
                        denominator_sessions_missing, missing_denominator_text, partial_reasons):
        """Un costo unitario solo se presenta como completo cuando nada impide atribuir el importe ni medir
        la cantidad; si falta algo se informa «información incompleta» y, como referencia, el valor parcial."""
        indicator = {'label': label, 'unit': unit, 'value': None, 'partial': None, 'status': 'unavailable', 'reasons': []}
        reasons = indicator['reasons']
        if not real['available']:
            reasons.append(real['reason'] or _('Costo real no disponible.'))
            return indicator
        if denominator <= 0:
            reasons.append(missing_denominator_text)
            return indicator
        if real['lines'] == 0:
            reasons.append(_('Sin gastos contabilizados atribuidos al vehículo en el período.'))
            return indicator
        incomplete = []
        if not pending['available']:
            incomplete.append(_('El gasto pendiente no se puede revisar con su perfil de acceso.'))
        if not unattributed['available']:
            incomplete.append(_('No se puede verificar si hay gastos del vehículo sin atribuir con su perfil de acceso.'))
        if unattributed['count']:
            incomplete.append(_('%(n)s gasto(s) de rendiciones que usan este vehículo no tienen vehículo asignado '
                                '(%(amount)s).') % {'n': unattributed['count'], 'amount': unattributed['amount']})
        if real.get('missing_rates'):
            incomplete.append(_('Sin tipo de cambio para: %s.') % ', '.join(real['missing_rates']))
        incomplete += partial_reasons
        if pending['available'] and pending['count']:
            incomplete.append(_('%s gasto(s) pendiente(s) aún no contabilizado(s) no están en el costo real.') % pending['count'])
        value = real['amount'] / denominator
        if incomplete:
            indicator.update(status='incomplete', partial=round(value, 4))
            reasons += incomplete
        else:
            indicator.update(status='ok', value=round(value, 4))
        return indicator

    # ------------------------------------------------------------------
    # Apuntes contables atribuidos a un vehículo
    # ------------------------------------------------------------------
    @api.model
    def _base_line_domain(self, company, date_from, date_to):
        return [('parent_state', '=', 'posted'), ('company_id', '=', company.id),
                ('date', '>=', date_from), ('date', '<=', date_to), ('display_type', 'in', ('product', False))]

    @api.model
    def _is_cost_line(self, line):
        return (line.account_id.account_type or '').startswith('expense')

    @api.model
    def _vehicle_posted_lines(self, company, vehicle, date_from, date_to):
        """Apuntes publicados de gasto que vienen de gastos atribuidos al vehículo, más las reversas de
        esos apuntes (nota de crédito / anulación), emparejadas por cuenta e importe inverso."""
        Line = self.env['account.move.line']
        base = self._base_line_domain(company, date_from, date_to)
        direct = Line.search(base + [('expense_id.step_vehicle_id', '=', vehicle.id)]).filtered(self._is_cost_line)
        rounding = company.currency_id.rounding
        candidates = Line.search(base + [
            ('expense_id', '=', False), ('move_id.reversed_entry_id', '!=', False),
            ('move_id.reversed_entry_id.line_ids.expense_id.step_vehicle_id', '=', vehicle.id)]).filtered(self._is_cost_line)
        matched, used = Line, Line
        for line in candidates:
            originals = line.move_id.reversed_entry_id.line_ids.filtered(
                lambda o: o.expense_id.step_vehicle_id == vehicle and o.account_id == line.account_id
                and float_compare(o.balance, -line.balance, precision_rounding=rounding) == 0) - used
            if originals:
                matched |= line
                used |= originals[:1]
        return direct | matched

    @api.model
    def _by_currency(self, lines):
        totals = {}
        for line in lines:
            totals[line.currency_id.name] = totals.get(line.currency_id.name, 0.0) + line.amount_currency
        return [{'currency': name, 'amount': round(amount, 2)} for name, amount in sorted(totals.items())]

    @api.model
    def _missing_rates(self, company, currencies):
        """Monedas extranjeras sin ningún tipo de cambio cargado: Odoo convertiría con 1:1 sin avisar."""
        foreign = currencies - company.currency_id
        return sorted(foreign.sudo().filtered(lambda c: not c.rate_ids).mapped('name'))

    @api.model
    def _account_tokens(self, distribution):
        """{account_id: porcentaje} de una distribución analítica; las claves combinadas «12,34» (varios planes)
        aportan su porcentaje a cada cuenta, una vez por clave."""
        shares = {}
        for raw_key, pct in (distribution or {}).items():
            for token in str(raw_key).split(','):
                try:
                    shares[int(token)] = shares.get(int(token), 0.0) + pct
                except (TypeError, ValueError):
                    continue
        return shares

    @api.model
    def _distribute(self, company, lines):
        Account = self.env['account.analytic.account']
        Center = self.env['step.management.cost.center']
        amounts, unassigned = {}, 0.0
        for line in lines:
            shares = self._account_tokens(line.analytic_distribution)
            assigned_pct = min(sum((line.analytic_distribution or {}).values()), 100.0)
            unassigned += line.balance * (100.0 - assigned_pct) / 100.0
            for account_id, pct in shares.items():
                amounts[account_id] = amounts.get(account_id, 0.0) + line.balance * pct / 100.0
        rows = []
        for account in Account.browse(list(amounts)).exists():
            centers = Center.search([('analytic_account_id', '=', account.id), ('company_id', '=', company.id)])
            rows.append({'account_id': account.id, 'account': account.display_name, 'plan': account.plan_id.display_name,
                         'center': centers[0].display_name if len(centers) == 1 else False,
                         'shared_account': len(centers) > 1, 'amount': self._money(company, amounts[account.id])})
        rows.sort(key=lambda row: -abs(row['amount']))
        return {'rows': rows, 'unassigned': self._money(company, unassigned)}

    @api.model
    def _unattributed_expenses(self, company, vehicle, date_from, date_to):
        lines = self.env['step.expense.vehicle.line'].search([
            ('vehicle_id', '=', vehicle.id), ('company_id', '=', company.id),
            ('date', '>=', date_from), ('date', '<=', date_to)])
        sheets = lines.sheet_id.filtered(lambda s: s.state != 'cancel')
        return self.env['hr.expense'].search([('sheet_id', 'in', sheets.ids), ('step_vehicle_id', '=', False)])

    @api.model
    def _documents(self, expenses):
        rows = []
        for expense in expenses:
            rows.append({
                'id': expense.id, 'name': expense.name, 'date': fields.Date.to_string(expense.date),
                'sheet_id': expense.sheet_id.id or False, 'folio': expense.sheet_id.folio or '',
                'state': expense.state, 'state_label': STATE_LABELS.get(expense.state, expense.state),
                'amount': expense.total_amount, 'original_amount': expense.total_amount_currency,
                'currency': expense.currency_id.name,
                'doc_type': dict(expense._fields['step_doc_type'].selection).get(expense.step_doc_type, ''),
                'doc_number': expense.step_doc_number or '',
            })
        return rows

    # ------------------------------------------------------------------
    # Centro de Gestión y Costos
    # ------------------------------------------------------------------
    @api.model
    def _center_sections(self, result, company, center, date_from, date_to):
        access = result['access']
        account = center.analytic_account_id
        if not account:
            result.update(real={'available': False, 'reason': _('El centro no tiene cuenta analítica vinculada.')},
                          pending={'available': False}, budget={'available': False, 'reason': _('Sin cuenta analítica.')},
                          quantities=None)
            return
        peers = self.env['step.management.cost.center'].search([
            ('analytic_account_id', '=', account.id), ('company_id', '=', company.id), ('id', '!=', center.id)])
        result['shared_account'] = peers.mapped('display_name')
        result['quantities'] = self._quantities(company, [('analytic_account_id', '=', account.id)], date_from, date_to)

        real = {'available': False, 'amount': None, 'lines': 0, 'reason': '',
                'basis': _('Apuntes publicados de cuentas de gasto, prorrateados por el porcentaje de la distribución '
                           'analítica de la cuenta del centro (misma lectura que Presupuesto vs. real).')}
        if access['accounting']:
            amount, count = self._center_real(company, account, date_from, date_to)
            real.update(available=True, amount=self._money(company, amount), lines=count)
        else:
            real['reason'] = _('Sin permiso de lectura contable.')
        result['real'] = real

        pending = {'available': False, 'amount': None, 'count': 0}
        if access['expenses']:
            total, count = 0.0, 0
            for expense in self._pending_expenses(company, date_from, date_to, [('analytic_distribution', 'in', [account.id])]):
                pct = self._account_tokens(expense.analytic_distribution).get(account.id, 0.0)
                if pct:
                    total += expense.total_amount * pct / 100.0
                    count += 1
            pending.update(available=True, amount=self._money(company, total), count=count)
        result['pending'] = pending
        result['budget'] = self._budget(company, center, peers, real, date_from, date_to)

    @api.model
    def _center_real(self, company, account, date_from, date_to):
        lines = self.env['account.move.line'].search(
            self._base_line_domain(company, date_from, date_to) + [('analytic_distribution', 'in', [account.id])])
        total, count = 0.0, 0
        for line in lines.filtered(self._is_cost_line):
            pct = self._account_tokens(line.analytic_distribution).get(account.id, 0.0)
            if pct:
                total += line.balance * pct / 100.0
                count += 1
        return total, count

    @api.model
    def _budget(self, company, center, peers, real, date_from, date_to):
        budget = {'available': False, 'amount': None, 'variance': None, 'variance_percent': None, 'reason': '',
                  'budgets': []}
        if not self.env['step.management.budget.month'].has_access('read'):
            budget['reason'] = _('Sin permiso de lectura de presupuestos.')
            return budget
        last_day = (date_to + timedelta(days=1)).day == 1
        if date_from.day != 1 or not last_day:
            budget['reason'] = _('El presupuesto es mensual: solo se compara con períodos de meses completos.')
            return budget
        if peers:
            budget['reason'] = _('Varias fichas (%s) comparten la cuenta analítica: el real no se puede separar por ficha.') % \
                ', '.join(peers.mapped('display_name'))
            return budget
        months = self.env['step.management.budget.month'].search([
            ('center_id', '=', center.id), ('budget_id.state', 'in', ('approved', 'closed')),
            ('budget_line_id.flow_type', '=', 'cost'), ('company_id', '=', company.id)])
        exchange = self.env['step.management.exchange.rate']
        total, budgets, missing = 0.0, set(), False
        for month in months:
            when = month.conversion_date
            if not when or not (date_from <= when <= date_to):
                continue
            conversion = exchange.get_conversion(month.amount, month.currency_id, company.currency_id, company, when, 'actual')
            # El servicio de conversión usa 1:1 cuando una moneda no tiene ninguna tasa cargada: aquí eso es «sin tipo de cambio».
            if not conversion['available'] or self._missing_rates(company, month.currency_id):
                missing = True
                continue
            total += conversion['amount']
            budgets.add(month.budget_id.display_name)
        if missing:
            budget['reason'] = _('Falta tipo de cambio para convertir el presupuesto a la moneda de la compañía.')
            return budget
        if not budgets:
            budget['reason'] = _('No hay presupuesto aprobado para este centro en el período.')
            return budget
        budget.update(available=True, amount=self._money(company, total), budgets=sorted(budgets))
        if len(budgets) > 1:
            budget['reason'] = _('Más de un presupuesto aprobado cubre el período: %s.') % ', '.join(sorted(budgets))
        if real['available']:
            budget['variance'] = self._money(company, real['amount'] - budget['amount'])
            budget['variance_percent'] = round(budget['variance'] * 100.0 / budget['amount'], 2) if budget['amount'] else None
        return budget
