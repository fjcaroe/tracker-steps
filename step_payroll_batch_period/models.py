"""Read-only local-period admission, followed by the actual payroll provider."""
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz
from psycopg2 import sql

from odoo import Command, fields, models, _
from odoo.exceptions import UserError

_PERIOD_SCOPE = object()


def _normal(records):
    return records.sudo(False)


def _dates(start, end):
    try:
        first, last = fields.Date.to_date(start), fields.Date.to_date(end)
    except (TypeError, ValueError):
        raise UserError(_('Seleccione un período de nómina válido.')) from None
    if not first or not last or first > last:
        raise UserError(_('Seleccione un período de nómina válido.'))
    return first, last


def _zone(contract):
    contract = _normal(contract)
    contract.ensure_one()
    contract.check_access('read')
    contract.check_field_access_rights('read', ['resource_calendar_id', 'employee_id', 'company_id'])
    calendar = contract.resource_calendar_id
    employee, company = contract.employee_id, contract.company_id
    calendar.check_access('read')
    calendar.check_field_access_rights('read', ['tz'])
    if calendar.tz:
        name = calendar.tz
    else:
        employee.check_access('read')
        employee.check_field_access_rights('read', ['tz'])
        name = employee.tz
        if not name:
            company.check_access('read')
            company.check_field_access_rights('read', ['resource_calendar_id'])
            fallback = company.resource_calendar_id
            fallback.check_access('read')
            fallback.check_field_access_rights('read', ['tz'])
            name = fallback.tz or 'UTC'
    try:
        return pytz.timezone(name)
    except pytz.UnknownTimeZoneError:
        raise UserError(_('El calendario del contrato no tiene una zona horaria válida.')) from None


def _midnight(zone, date):
    value = datetime.combine(date, time.min)
    # Santiago can skip midnight. Use the first real minute. Ambiguous midnight
    # starts at its first occurrence, preserving both in the civil day.
    for _minute in range(24 * 60 + 1):
        try:
            return zone.localize(value, is_dst=None).astimezone(pytz.UTC).replace(tzinfo=None)
        except pytz.AmbiguousTimeError:
            return min(zone.localize(value, is_dst=flag).astimezone(pytz.UTC).replace(tzinfo=None)
                       for flag in (True, False))
        except pytz.NonExistentTimeError:
            value += timedelta(minutes=1)
    raise UserError(_('El período requiere revisar una fecha local inexistente.'))


def period_bounds(contract, start, end):
    first, last = _dates(start, end)
    zone = _zone(contract)
    return _midnight(zone, first), _midnight(zone, last + timedelta(days=1))


def _oca(env):
    # Registry provenance only; never authorization for business data.
    env.cr.execute("SELECT name FROM ir_module_module WHERE name IN ('payroll','hr_payroll') AND state IN ('installed','to upgrade','to install','to remove')")
    installed = {row[0] for row in env.cr.fetchall()}
    if installed == {'payroll', 'hr_payroll'}:
        raise UserError(_('Revise la identidad del motor de nómina antes de generar el lote.'))
    return installed == {'payroll'}


def _scope(context):
    value = context.get('_steps_batch_period')
    return value if isinstance(value, tuple) and len(value) == 5 and value[0] is _PERIOD_SCOPE else None


def _public_result(value):
    """Never return the server-only capability in a provider action context."""
    if isinstance(value, dict):
        return {key: _public_result(item) for key, item in value.items() if key != '_steps_batch_period'}
    if isinstance(value, (tuple, list)):
        return type(value)(_public_result(item) for item in value)
    return value


class WorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    def _step_entries_in_batch_period(self, start, end):
        normal = _normal(self).with_context(active_test=True)
        normal.check_access('read')
        normal.check_field_access_rights('read', ['contract_id', 'date_start', 'date_stop'])
        bounds = {}
        def intersects(entry):
            contract = entry.contract_id
            if contract.id not in bounds:
                bounds[contract.id] = period_bounds(contract, start, end)
            first, last = bounds[contract.id]
            return entry.date_start < last and entry.date_stop > first
        return normal.filtered(intersects)

    def _check_if_error(self):
        scope = _scope(self.env.context)
        if scope:
            # Keep the native buffer hook. Admission itself never calls this
            # checker: the official implementation changes conflict states.
            relevant = self._step_entries_in_batch_period(scope[2], scope[3])
            return super(WorkEntry, relevant.with_context(_steps_batch_period=None))._check_if_error()
        return super()._check_if_error()


class PayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'

    def _step_batch_period_preflight(self):
        normal = _normal(self).with_context(active_test=True)
        normal.ensure_one()
        normal.check_access('read')
        normal.check_field_access_rights('read', ['employee_ids'])
        active_id = normal.env.context.get('active_id')
        if (type(active_id) is not int or active_id <= 0
                or normal.env.context.get('active_model') not in (None, 'hr.payslip.run')):
            raise UserError(_('Abra el asistente desde un lote de nómina real.'))
        run = normal.env['hr.payslip.run'].browse(active_id)
        run.check_access('read')
        run.check_field_access_rights('read', ['company_id', 'state', 'date_start', 'date_end'])
        if not run.exists() or run.state != 'draft':
            raise UserError(_('Seleccione un lote de nómina existente y abierto.'))
        if run.company_id != normal.env.company:
            raise UserError(_('Seleccione la compañía del lote antes de generar nómina.'))
        first, last = _dates(run.date_start, run.date_end)
        relation = normal._fields['employee_ids']
        normal.flush_recordset(['employee_ids'])
        normal.env.cr.execute(sql.SQL('SELECT {} FROM {} WHERE {}=%s').format(
            sql.Identifier(relation.column2), sql.Identifier(relation.relation), sql.Identifier(relation.column1)), (normal.id,))
        employees = normal.env['hr.employee'].with_context(active_test=False).browse([row[0] for row in normal.env.cr.fetchall()])
        employees.check_access('read')
        employees.check_field_access_rights('read', ['company_id', 'name', 'active'])
        if not employees or any(not employee.active or employee.company_id != run.company_id for employee in employees):
            raise UserError(_('Seleccione trabajadores activos de la compañía del lote.'))
        normal.env['hr.payslip'].flush_model(['payslip_run_id', 'employee_id'])
        normal.env.cr.execute('SELECT id FROM hr_payslip WHERE payslip_run_id=%s AND employee_id=ANY(%s)', (run.id, employees.ids))
        existing = normal.env['hr.payslip'].browse([row[0] for row in normal.env.cr.fetchall()])
        existing.check_access('read')
        if existing:
            raise UserError(_('El lote ya contiene liquidaciones de los trabajadores seleccionados; revise sus registros originales.'))
        oca = _oca(normal.env)
        states = ['open'] if oca else ['open', 'close']
        model = normal.env['hr.contract'].with_context(active_test=True)
        names = ['employee_id', 'company_id', 'state', 'date_start', 'date_end', 'resource_calendar_id']
        if 'active' in model._fields:
            names.append('active')
        model.flush_model(names)
        active = ' AND active' if 'active' in model._fields else ''
        normal.env.cr.execute('''SELECT id FROM hr_contract WHERE employee_id=ANY(%s) AND state=ANY(%s)
            AND date_start<=%s AND (date_end IS NULL OR date_end>=%s)''' + active, (employees.ids, states, last, first))
        contracts = model.browse([row[0] for row in normal.env.cr.fetchall()])
        contracts.check_access('read')
        contracts.check_field_access_rights('read', names)
        selected = employees.with_context(active_test=True)._get_contracts(first, last, states=states)
        selected.check_access('read')
        if set(selected.ids) != set(contracts.ids):
            raise UserError(_('La selección de contratos del período está incompleta.'))
        for employee in employees:
            own = contracts.filtered(lambda contract: contract.employee_id == employee)
            if not own or any(contract.company_id != run.company_id for contract in own) or (oca and len(own) != 1):
                raise UserError(_('El período requiere contratos reales e inequívocos de la compañía del lote.'))
        if 'step_payroll_migration_review' in contracts._fields:
            contracts.check_field_access_rights('read', ['step_payroll_migration_review'])
            if any(contract.step_payroll_migration_review for contract in contracts):
                raise UserError(_('Confirme la revisión de parámetros de los contratos antes de generar el lote.'))
        known_chile = normal.env.ref('l10n_cl_simpledigital_payroll.structure_chile', raise_if_not_found=False)
        for contract in contracts:
            structure = normal.env['hr.payroll.structure']
            if 'structure_id' in normal._fields:
                normal.check_field_access_rights('read', ['structure_id'])
                structure = normal.structure_id
            if not structure and 'struct_id' in run._fields:
                run.check_field_access_rights('read', ['struct_id'])
                structure = run.struct_id
            if not structure and 'struct_id' in contract._fields:
                contract.check_field_access_rights('read', ['struct_id'])
                structure = contract.struct_id
            structure.check_access('read')
            if 'step_legacy_payroll' in structure._fields:
                structure.check_field_access_rights('read', ['step_legacy_payroll'])
                if any(record.step_legacy_payroll for record in structure):
                    raise UserError(_('La estructura histórica no se recalcula desde este lote.'))
            if structure and structure == known_chile and hasattr(contract, '_step_simpledigital_review_issues'):
                review_fields = [name for name in ('health_institution', 'pension_option', 'income_tax_type',
                    'work_schedule_id', 'analytic_account_id', 'contract_type_id', 'afp_option') if name in contract._fields]
                contract.check_field_access_rights('read', review_fields)
                if 'hr_commune' in contract.employee_id._fields:
                    contract.employee_id.check_field_access_rights('read', ['hr_commune'])
                if contract._step_simpledigital_review_issues():
                    raise UserError(_('Complete los parámetros originales de Simple Digital antes de generar el lote.'))
        entries_model = normal.env['hr.work.entry'].with_context(active_test=False)
        entry_names = ['contract_id', 'employee_id', 'company_id', 'date_start', 'date_stop', 'state', 'active', 'work_entry_type_id']
        entries_model.flush_model(entry_names)
        entries = entries_model.browse()
        bounds = {}
        for contract in contracts:
            bounds[contract.id] = period_bounds(contract, first, last)
            lower, upper = bounds[contract.id]
            normal.env.cr.execute('''SELECT id FROM hr_work_entry WHERE contract_id=%s AND active
                AND state!='cancelled' AND date_start<%s AND date_stop>%s''', (contract.id, upper, lower))
            entries |= entries_model.browse([row[0] for row in normal.env.cr.fetchall()])
        entries.check_access('read')
        entries.check_field_access_rights('read', entry_names)
        if any(entry.company_id != run.company_id or entry.employee_id != entry.contract_id.employee_id for entry in entries):
            raise UserError(_('Las entradas deben conservar su contrato, trabajador y compañía originales.'))
        entries.work_entry_type_id.check_access('read')
        entries.work_entry_type_id.check_field_access_rights('read', ['code', 'country_id'])
        run.company_id.check_access('read')
        run.company_id.check_field_access_rights('read', ['country_id'])
        if any(kind.country_id and kind.country_id != run.company_id.country_id for kind in entries.work_entry_type_id):
            raise UserError(_('El tipo de entrada debe corresponder al país de la compañía del lote o ser compartido.'))
        conflicts = entries.filtered(lambda entry: entry.state == 'conflict' or not entry.work_entry_type_id)
        by_employee = defaultdict(list)
        for entry in entries:
            lower, upper = bounds[entry.contract_id.id]
            left, right = max(entry.date_start, lower), min(entry.date_stop, upper)
            for earlier, earlier_left, earlier_right in by_employee[entry.employee_id.id]:
                if left < earlier_right and right > earlier_left:
                    conflicts |= entry | earlier
            by_employee[entry.employee_id.id].append((entry, left, right))
        return {'run': run, 'employees': employees, 'contracts': contracts, 'entries': entries,
                'conflicts': conflicts, 'start': first, 'end': last, 'oca': oca}

    def compute_sheet(self):
        normal = _normal(self).with_context(active_test=True)
        data = normal._step_batch_period_preflight()
        if data['conflicts']:
            lines = []
            for entry in data['conflicts'].sorted(key=lambda row: (row.employee_id.name or '', row.date_start, row.id)):
                zone = _zone(entry.contract_id)
                first = pytz.UTC.localize(entry.date_start).astimezone(zone)
                last = pytz.UTC.localize(entry.date_stop).astimezone(zone)
                lines.append('%s: %s → %s (%s; entrada %s)' % (
                    entry.employee_id.name, first.strftime('%d/%m/%Y %H:%M'),
                    last.strftime('%d/%m/%Y %H:%M'), zone.zone, entry.id))
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Conflictos de entradas de trabajo en el período de nómina'),
                'message': _('Revise las entradas indicadas antes de generar el lote:\n%s', '\n'.join(lines)), 'sticky': True}}
        if data['oca']:
            data['run'].check_field_access_rights('read', ['struct_id'])
            for contract in data['contracts']:
                contract.check_field_access_rights('read', ['struct_id'])
                structure = data['run'].struct_id or contract.struct_id
                structure.check_access('read')
                structure.check_field_access_rights('read', ['use_work_entries'])
                if not structure or not structure.use_work_entries:
                    raise UserError(_('El lote Community requiere la política real de entradas de trabajo.'))
                if contract.date_start > data['start'] or (contract.date_end and contract.date_end < data['end']):
                    raise UserError(_('El período parcial del contrato requiere una política certificada antes de generar el lote Community.'))
                if not contract.get_work_hours(data['start'], data['end']):
                    raise UserError(_('Registre entradas reales del período antes de generar el lote Community.'))
                preview = normal.env['hr.payslip'].new({'employee_id': contract.employee_id.id,
                    'company_id': contract.company_id.id, 'contract_id': contract.id, 'struct_id': structure.id,
                    'date_from': data['start'], 'date_to': data['end']})
                actual_days = preview._get_worked_day_lines()
                preview.worked_days_line_ids = [Command.create(values) for values in actual_days]
                preview._step_check_original_configuration(operation='calculate')
        capability = (_PERIOD_SCOPE, data['run'].id, data['start'], data['end'],
                      tuple((contract.employee_id.id, contract.id) for contract in data['contracts']))
        context = {'_steps_batch_period': capability}
        if data['oca']:
            context['contract'] = True
        with normal.env.cr.savepoint():
            return _public_result(super(PayslipEmployees, normal.with_context(**context)).compute_sheet())


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def get_payslip_vals(self, date_from, date_to, employee_id=False, contract_id=False, struct_id=False):
        scope = _scope(self.env.context)
        if not scope or not _oca(self.env):
            return super().get_payslip_vals(date_from, date_to, employee_id, contract_id, struct_id)
        normal = _normal(self).with_context(active_test=True)
        if (_dates(date_from, date_to) != scope[2:4] or normal.env.context.get('active_id') != scope[1]
                or employee_id not in dict(scope[4]) or normal.env.context.get('contract') is not True):
            raise UserError(_('El contexto interno del período de nómina no coincide con el lote.'))
        result = super(Payslip, normal).get_payslip_vals(date_from, date_to, employee_id, contract_id, struct_id)
        values = result['value']
        if values.get('contract_id') != dict(scope[4])[employee_id]:
            raise UserError(_('El proveedor cambió el contrato original del período.'))
        contract = normal.env['hr.contract'].browse(values['contract_id'])
        structure = normal.env['hr.payroll.structure'].browse(values.get('struct_id'))
        contract.check_access('read')
        contract.check_field_access_rights('read', ['struct_id', 'company_id'])
        structure.check_access('read')
        structure.check_field_access_rights('read', ['use_work_entries'])
        run = normal.env['hr.payslip.run'].browse(scope[1])
        run.check_access('read')
        run.check_field_access_rights('read', ['struct_id'])
        if structure != (run.struct_id or contract.struct_id):
            raise UserError(_('El proveedor cambió la estructura original del período.'))
        structure._step_check_payroll_scope(contract.company_id)
        if not structure.use_work_entries:
            raise UserError(_('El lote Community requiere la política real de entradas de trabajo.'))
        # Actual ORM onchange/preview object, discarded after reading the API.
        # Never compute_sheet, a persisted placeholder or an invented master.
        preview = normal.new({'employee_id': employee_id, 'company_id': contract.company_id.id,
            'contract_id': contract.id, 'struct_id': structure.id, 'date_from': date_from, 'date_to': date_to})
        values['worked_days_line_ids'] = preview._get_worked_day_lines()
        return result
