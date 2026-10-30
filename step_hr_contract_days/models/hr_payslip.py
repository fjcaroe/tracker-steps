from calendar import monthrange
from datetime import datetime, time

from odoo import fields, models, _
from odoo.exceptions import UserError

LATE_CODE = "LEAVECL131"
HOURS_PER_DAY = 8.0


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _step_contract_days_access(self, write=False, sources=False):
        """Authorize complete original rows before any provider calculation.

        SQL collects physical identities only. It never supplies payroll values
        or grants access to a row hidden by the caller's normal record rules.
        No dependency on an Enterprise-only payroll helper is introduced.
        """
        normal = self.sudo(False)
        normal.check_access('write' if write else 'read')
        names = ['state', 'struct_id', 'contract_id', 'employee_id', 'company_id',
                 'date_from', 'date_to', 'worked_days_line_ids']
        names += [name for name in ('paid', 'step_history_locked') if name in normal._fields]
        normal.check_field_access_rights('read', names)
        for slip in normal:
            original = slip if type(slip.id) is int else slip._origin
            if original and type(original.id) is int:
                original.check_access('read')
                original.check_field_access_rights('read', names)
                if (original.state not in ('draft', 'verify')
                        or 'paid' in original._fields and original.paid
                        or 'step_history_locked' in original._fields and original.step_history_locked):
                    raise UserError(_('Closed payroll history cannot be recalculated.'))
        # Inspect every selected state before even flushing source identities.
        for slip in normal:
            slip.struct_id.check_access('read')
            slip.struct_id.check_field_access_rights('read', ['name'])
            if slip.struct_id.name != 'Nómina Chile':
                continue
            if write and type(slip.id) is not int:
                raise UserError(_('Save the real draft payslip before calculating contract days.'))
            contract = slip.contract_id
            contract.check_access('read')
            contract.check_field_access_rights('read', ['date_start', 'date_end', 'wage', 'wage_type',
                'employee_id', 'company_id', 'resource_calendar_id'])
            slip.employee_id.check_access('read')
            if type(slip.id) is int:
                days = normal.env['hr.payslip.worked_days']
                days.check_access('read')
                days.check_field_access_rights('read', ['payslip_id', 'sequence', 'work_entry_type_id',
                    'number_of_days', 'number_of_hours', 'amount'])
                if write:
                    days.check_access('write')
                    days.check_field_access_rights('write', ['number_of_days', 'number_of_hours', 'amount'])
                days.flush_model(['payslip_id', 'work_entry_type_id'])
                normal.env.cr.execute('SELECT id,work_entry_type_id FROM hr_payslip_worked_days WHERE payslip_id=%s', (slip.id,))
                rows = normal.env.cr.fetchall()
                complete = days.browse([row[0] for row in rows])
                complete.check_access('write' if write else 'read')
                types = normal.env['hr.work.entry.type'].browse([row[1] for row in rows if row[1]])
                types.check_access('read')
                types.check_field_access_rights('read', ['code', 'sequence', 'is_leave', 'active'])
            if sources and type(slip.employee_id.id) is int and slip.date_from and slip.date_to:
                slip._step_contract_days_source_access()
        return normal

    def _step_contract_days_source_access(self):
        self.ensure_one()
        normal = self.sudo(False)
        entries, leaves, leave_types, types = (normal.env[name] for name in
            ('hr.work.entry', 'hr.leave', 'hr.leave.type', 'hr.work.entry.type'))
        for records, names in ((entries, ['employee_id', 'contract_id', 'company_id', 'work_entry_type_id',
                    'date_start', 'date_stop', 'state', 'duration']),
                (leaves, ['employee_id', 'holiday_status_id', 'state', 'date_from', 'date_to']),
                (leave_types, ['unpaid', 'work_entry_type_id']),
                (types, ['code', 'is_leave', 'active', 'sequence'])):
            records.check_access('read')
            records.check_field_access_rights('read', names)
        start = datetime.combine(fields.Date.to_date(normal.date_from), time.min)
        stop = datetime.combine(fields.Date.to_date(normal.date_to), time.max)
        entry_start, entry_stop = start, stop
        if hasattr(normal.contract_id, '_payroll_period_bounds') and normal.contract_id.resource_calendar_id:
            left, right = normal.contract_id._payroll_period_bounds(normal.date_from, normal.date_to)
            entry_start, entry_stop = min(start, left), max(stop, right)
        entries.flush_model(['employee_id', 'work_entry_type_id', 'date_start', 'date_stop', 'state'])
        normal.env.cr.execute("SELECT e.id,e.work_entry_type_id FROM hr_work_entry e "
            "LEFT JOIN hr_work_entry_type t ON t.id=e.work_entry_type_id WHERE e.employee_id=%s "
            "AND (e.contract_id=%s OR t.code=%s) AND e.state!='cancelled' AND e.date_start<=%s AND e.date_stop>=%s",
            (normal.employee_id.id, normal.contract_id.id, LATE_CODE, entry_stop, entry_start))
        work_rows = normal.env.cr.fetchall()
        entries.browse([row[0] for row in work_rows]).check_access('read')
        type_ids = {row[1] for row in work_rows if row[1]}
        if type(normal.id) is int:
            normal.env['hr.payslip.worked_days'].flush_model(['payslip_id', 'work_entry_type_id'])
            normal.env.cr.execute('SELECT work_entry_type_id FROM hr_payslip_worked_days WHERE payslip_id=%s', (normal.id,))
            type_ids.update(row[0] for row in normal.env.cr.fetchall() if row[0])
        types.browse(sorted(type_ids)).check_access('read')
        leaves.flush_model(['employee_id', 'holiday_status_id', 'state', 'date_from', 'date_to'])
        normal.env.cr.execute("SELECT id,holiday_status_id FROM hr_leave WHERE employee_id=%s AND state='validate' "
            'AND date_from<=%s AND date_to>=%s', (normal.employee_id.id, stop, start))
        leave_rows = normal.env.cr.fetchall()
        leaves.browse([row[0] for row in leave_rows]).check_access('read')
        masters = leave_types.browse([row[1] for row in leave_rows if row[1]])
        masters.check_access('read')
        masters.work_entry_type_id.check_access('read')
        leave_types.flush_model(['unpaid', 'work_entry_type_id'] + (['active'] if 'active' in leave_types._fields else []))
        types.flush_model(['code'])
        active = " AND l.active" if 'active' in leave_types._fields and normal.env.context.get('active_test', True) else ''
        normal.env.cr.execute('SELECT l.id FROM hr_leave_type l JOIN hr_work_entry_type t ON t.id=l.work_entry_type_id '
            "WHERE l.unpaid AND t.code='LEAVECL130' AND t.id=ANY(%s)" + active, (sorted(type_ids),))
        leave_types.browse([row[0] for row in normal.env.cr.fetchall()]).check_access('read')

    def compute_sheet(self):
        try:
            # Do not flush unrelated salary computations before admission.
            with self.env.cr.savepoint(flush=False):
                normal = self._step_contract_days_access(write=True, sources=True)
                result = normal._step_compute_contract_days_sheet()
                normal.env.flush_all()
                return result
        except Exception:
            # A nonflushing savepoint rolls SQL back but does not clear ORM
            # caches. Match the official flushing-savepoint failure contract
            # so a caller catching an error cannot later flush stale days.
            self.env.cr.clear()
            raise

    def _step_compute_contract_days_sheet(self):
        # Native Compute Sheet does not regenerate stored worked-day lines.
        # Refresh only the affected attendance, retaining source absences,
        # inputs and all paid/done slips. Existing lateness is applied once.
        for slip in self.filtered(lambda row:row.state in ('draft','verify')):
            values=[{'sequence':line.sequence,'work_entry_type_id':line.work_entry_type_id.id,
                     'number_of_days':line.number_of_days,'number_of_hours':line.number_of_hours,
                     'amount':line.amount} for line in slip.worked_days_line_ids]
            before=[dict(line) for line in values]
            corrected=slip._step_monthly_absence_days(values)
            if corrected==before:
                continue
            corrected=slip._step_deduct_late_hours(corrected)
            for line in corrected:
                entry=slip.env['hr.work.entry.type'].browse(line['work_entry_type_id'])
                if entry.code!='WORK100':
                    continue
                stored=slip.worked_days_line_ids.filtered(lambda row:row.work_entry_type_id==entry)
                assert len(stored)<=1
                if stored:
                    stored.write({key:line[key] for key in ('number_of_days','number_of_hours','amount')})
                else:
                    slip.env['hr.payslip.worked_days'].create(dict(line,payslip_id=slip.id))
        return super().compute_sheet()

    def _get_worked_day_lines_values(self, domain=None):
        normal = self._step_contract_days_access(sources=True)
        lines = super(HrPayslip, normal)._get_worked_day_lines_values(domain=domain)
        lines = normal._step_contract_days_lines(lines)
        lines = normal._step_monthly_absence_days(lines)
        return normal._step_deduct_late_hours(lines)

    def _step_monthly_absence_days(self, lines):
        """Full-month fixed wages: unjustified absence is deducted from 30.

        The provider groups FALT with medical leave and selects base/divisor 31.
        Keep medical leave and partial-contract policies outside this correction.
        Source leaves/work entries and already stored payslips are never edited.
        """
        self.ensure_one()
        start, end, contract = self.date_from, self.date_to, self.contract_id
        if (self.struct_id.name != 'Nómina Chile' or contract.wage_type!='monthly' or not start or not end
                or (start.year,start.month)!=(end.year,end.month) or start.day!=1
                or end.day!=monthrange(end.year,end.month)[1]
                or not contract.date_start or contract.date_start>start
                or contract.date_end and contract.date_end<end):
            return lines
        types=self.env['hr.work.entry.type']
        by_code={}
        for line in lines:
            by_code.setdefault(types.browse(line['work_entry_type_id']).code,[]).append(line)
        days=lambda code:sum(line.get('number_of_days',0.0) for line in by_code.get(code,[]))
        # LEAVECL130 in the reported catalog is linked to the native unpaid
        # time-off master, not medical leave. Retain that relation and its IDs.
        unpaid=self.env['hr.leave.type'].search([
            ('unpaid','=',True),('work_entry_type_id.code','=','LEAVECL130')]).mapped('work_entry_type_id').ids
        additional=sum(line.get('number_of_days',0.0) for line in by_code.get('LEAVECL130',[])
                       if line['work_entry_type_id'] in unpaid)
        medical130=days('LEAVECL130')-additional
        absent=days('FALT')+additional
        if absent<=0 or days('LIC')>0 or days('ACCTR')>0 or medical130>0:
            return lines
        attendance=max(30.0-absent-days('LEAVECL120'),0.0)
        work=(by_code.get('WORK100') or [None])[0]
        if work is None and attendance:
            entry=types.search([('code','=','WORK100')],limit=1)
            if entry:
                work={'sequence':entry.sequence,'work_entry_type_id':entry.id};lines.append(work)
        if work is not None:
            work.update(number_of_days=attendance,number_of_hours=attendance*HOURS_PER_DAY,
                        amount=contract.wage/30.0*attendance)
        return lines

    def _step_late_hours(self):
        """Horas de atraso (entradas LEAVECL131) del trabajador en el período."""
        self.ensure_one()
        start = datetime.combine(fields.Date.to_date(self.date_from), time.min)
        end = datetime.combine(fields.Date.to_date(self.date_to), time.max)
        entries = self.env["hr.work.entry"].search([
            ("employee_id", "=", self.employee_id.id),
            ("work_entry_type_id.code", "=", LATE_CODE),
            ("state", "!=", "cancelled"),
            ("date_start", ">=", start),
            ("date_start", "<=", end),
        ])
        return sum(entries.mapped("duration"))

    def _step_deduct_late_hours(self, lines):
        """Descuenta del sueldo base las horas no trabajadas por atrasos.

        El motor del proveedor arma la asistencia como 30 días menos licencias,
        faltas y vacaciones, e ignora LEAVECL131. Las horas se convierten a días
        (8 h = 1 día, convención del motor) y se restan de WORK100, proporcional
        al importe ya calculado. No cambia los días previsionales (Previred solo
        resta licencias/faltas/etc.).
        """
        if self.struct_id.name != "Nómina Chile" or not self.employee_id:
            return lines
        late_hours = self._step_late_hours()
        if late_hours <= 0:
            return lines
        entry_types = self.env["hr.work.entry.type"]
        by_code = {}
        for line in lines:
            by_code.setdefault(entry_types.browse(line["work_entry_type_id"]).code, line)
        attendance = by_code.get("WORK100")
        late_days = late_hours / HOURS_PER_DAY
        old_days = attendance.get("number_of_days", 0.0) if attendance else 0.0
        if attendance is not None and old_days > 0:
            new_days = max(old_days - late_days, 0.0)
            old_amount = attendance.get("amount") or self.contract_id.wage / 30.0 * old_days
            attendance.update({
                "number_of_days": new_days,
                "number_of_hours": new_days * HOURS_PER_DAY,
                "amount": old_amount * new_days / old_days,
            })
        late_line = by_code.get(LATE_CODE)
        if late_line is None:
            late_type = entry_types.search([("code", "=", LATE_CODE)], limit=1)
            if late_type:
                late_line = {"sequence": late_type.sequence, "work_entry_type_id": late_type.id}
                lines.append(late_line)
        if late_line is not None:
            late_line.update({
                "number_of_days": late_days,
                "number_of_hours": late_hours,
                "amount": 0.0,
            })
        return lines

    def _step_contract_days_lines(self, lines):
        contract = self.contract_id
        if not (
            self.struct_id.name == "Nómina Chile"
            and contract.date_start
            and contract.date_end
            and self.date_from < contract.date_start <= contract.date_end < self.date_to
        ):
            return lines

        # SimpleDigital already bounds the base to the contract's actual
        # duration on a mid-period exit. Subtracting pre-entry days again
        # understates attendance (e.g. a 9-day contract becomes 2 days).
        # Rebuild attendance from that bounded duration and the normalized
        # leave lines, so absences still work when the old result hit zero.
        entry_types = self.env["hr.work.entry.type"]
        leave_codes = {"LIC", "LEAVECL130", "FALT", "LEAVECL120"}
        leave_days = sum(
            line.get("number_of_days", 0.0)
            for line in lines
            if entry_types.browse(line["work_entry_type_id"]).code in leave_codes
        )
        days = max((contract.date_end - contract.date_start).days + 1 - leave_days, 0.0)
        divisor = 31.0 if (self.date_to - self.date_from).days + 1 == 31 else 30.0
        attendance = next(
            (line for line in lines
             if entry_types.browse(line["work_entry_type_id"]).code == "WORK100"),
            None,
        )
        if attendance is None and days:
            work_type = entry_types.search([("code", "=", "WORK100")], limit=1)
            if work_type:
                attendance = {"sequence": work_type.sequence, "work_entry_type_id": work_type.id}
                lines.append(attendance)
        if attendance is not None:
            attendance.update({
                "number_of_days": days,
                "number_of_hours": days * 8,
                "amount": contract.wage / divisor * days,
            })
        return lines
