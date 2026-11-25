"""Harvest enrollment and attendance keep the native employee and attendance tables."""
import hashlib
import json
import re
from datetime import datetime, timezone

import pytz

from odoo import Command, api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def event_time(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if not result.tzinfo:
            raise ValueError('Timezone required')
        return result.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError):
        raise ValidationError(_('Indique una fecha y hora de asistencia válidas, con zona horaria.'))


class HarvestEmployee(models.Model):
    _inherit = 'hr.employee'

    harvest_enrollment_uid = fields.Char(copy=False, index=True)
    harvest_enrollment_fingerprint = fields.Char(copy=False)
    _sql_constraints = [
        ('harvest_enrollment_company_unique', 'unique(company_id, harvest_enrollment_uid)',
         'Este enrolamiento Harvest ya fue recibido.'),
    ]


class HarvestAttendance(models.Model):
    _inherit = 'hr.attendance'

    harvest_crew_id = fields.Many2one('hr.salary.custom', string='Cuadrilla Harvest', ondelete='restrict', index=True, copy=False)
    harvest_uid = fields.Char(copy=False, index=True)
    harvest_fingerprint = fields.Char(copy=False)
    _sql_constraints = [
        ('harvest_uid_employee_unique', 'unique(employee_id, harvest_uid)',
         'Esta asistencia Harvest ya fue recibida.'),
    ]

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        # Stage one is operational Cosecha attendance. Keep the native table,
        # but do not expose its rows to HR dashboards or payroll consumers.
        cosecha = self.env.context.get('harvest_attendance_scope') == 'cosecha'
        scope = [('harvest_crew_id', '!=' if cosecha else '=', False)]
        return super()._search(expression.AND([domain, scope]), offset=offset, limit=limit, order=order)

    def _get_attendances_dates(self):
        ordinary = self.filtered(lambda row: not row.harvest_crew_id)
        return super(HarvestAttendance, ordinary)._get_attendances_dates()

    def _update_overtime(self, employee_attendance_dates=None):
        ordinary = self.filtered(lambda row: not row.harvest_crew_id).with_context(harvest_attendance_scope=False)
        return super(HarvestAttendance, ordinary)._update_overtime(employee_attendance_dates)

    def _create_work_entries(self):
        ordinary = self.filtered(lambda row: not row.harvest_crew_id).with_context(harvest_attendance_scope=False)
        if ordinary:
            return super(HarvestAttendance, ordinary)._create_work_entries()

    def _compute_overtime_hours(self):
        # Upstream uses raw SQL, so its allocation must also exclude operational
        # rows when computing an ordinary HR record for the same employee/day.
        cosecha = self.filtered('harvest_crew_id')
        cosecha.overtime_hours = 0
        ordinary = self - cosecha
        ordinary.overtime_hours = 0
        if not ordinary:
            return
        rows = self.with_context(harvest_attendance_scope=False).search([
            ('employee_id', 'in', ordinary.employee_id.ids), ('check_in', '!=', False),
        ], order='check_in desc,id desc')
        by_day = {}
        for row in rows:
            zone = pytz.timezone(row.employee_id.resource_calendar_id.tz or row.employee_id.resource_id.tz or 'UTC')
            day = row.check_in.replace(tzinfo=timezone.utc).astimezone(zone).date()
            by_day.setdefault((row.employee_id.id, day), []).append(row)
        for overtime in self.env['hr.attendance.overtime'].search([
                ('employee_id', 'in', ordinary.employee_id.ids), ('adjustment', '=', False)]):
            remaining = overtime.duration
            for position, row in enumerate(by_day.get((overtime.employee_id.id, overtime.date), [])):
                hours = row.worked_hours
                value = min(hours, max(0, remaining)) if hours else 0
                if remaining < 0 and position == 0 and hours:
                    value = remaining
                if row in ordinary:
                    row.overtime_hours = value
                remaining -= max(0, value)

    def write(self, values):
        if 'harvest_crew_id' in values and any(
                row.harvest_crew_id and values['harvest_crew_id'] != row.harvest_crew_id.id for row in self):
            raise ValidationError(_('La asistencia de Cosecha conserva su cuadrilla; su integración con RR. HH. corresponde a una etapa posterior.'))
        return super().write(values)

    @api.constrains('harvest_crew_id', 'employee_id')
    def _check_harvest_crew(self):
        for record in self.filtered('harvest_crew_id'):
            record.harvest_crew_id._harvest_check_worker(record.employee_id)


class HarvestCrew(models.Model):
    _inherit = 'hr.salary.custom'

    def _harvest_check_crew(self):
        self.ensure_one()
        self.check_access('read')
        if self.company_id != self.env.company or self.group_type not in ('propio', 'contratista'):
            raise ValidationError(_('Seleccione una cuadrilla de la empresa activa.'))
        if self.group_type == 'contratista' and not self.partner_id:
            raise ValidationError(_('La cuadrilla requiere su contratista nativo.'))

    def _harvest_members(self):
        return self.salary_line.employee_id | self.contract_line.employee_id

    def _harvest_check_worker(self, worker, member=True):
        self._harvest_check_crew()
        worker.check_access('read')
        if worker.company_id != self.company_id:
            raise ValidationError(_('El trabajador pertenece a otra empresa.'))
        contractor = worker.contratista_id if worker.is_contratista else False
        if (self.group_type == 'propio' and contractor) or (
                self.group_type == 'contratista' and contractor != self.partner_id):
            raise ValidationError(_('El trabajador no corresponde al tipo y contratista de la cuadrilla.'))
        if member and worker not in self._harvest_members():
            raise ValidationError(_('El trabajador no pertenece a esta cuadrilla.'))

    def harvest_enroll_worker(self, data):
        self._harvest_check_crew()
        self.check_access('write')
        event_uid = str(data.get('client_uuid') or '').strip()
        name = str(data.get('name') or '').strip()
        pin = str(data.get('nip') or '').strip()
        gender = {'M': 'male', 'F': 'female', 'O': 'other'}.get(data.get('sex'))
        if not event_uid or len(event_uid) > 100 or not name or len(name) > 256 or not re.fullmatch(r'\d{1,8}', pin) or not gender:
            raise ValidationError(_('Complete nombre, NIP numérico (hasta 8 dígitos), sexo y cargo.'))
        digest = fingerprint({key: data.get(key) for key in ('client_uuid', 'crew_id', 'name', 'nip', 'sex', 'job_id')})
        employees = self.env['hr.employee'].with_context(active_test=False)
        employees.check_access('create')
        existing = employees.search([('company_id', '=', self.company_id.id), ('harvest_enrollment_uid', '=', event_uid)], limit=1)
        if existing:
            if existing.harvest_enrollment_fingerprint != digest:
                raise ValidationError(_('Un enrolamiento recibido no puede reenviarse con otros datos.'))
            self._harvest_check_worker(existing)
            return existing
        if employees.search_count([('company_id', '=', self.company_id.id), ('pin', '=', pin)]):
            raise ValidationError(_('El NIP ya existe en esta empresa. Seleccione el trabajador del maestro.'))
        jobs = self.env['hr.job']
        if data.get('job_id'):
            job = jobs.browse(int(data['job_id'])).exists()
            job.check_access('read')
            if not job or job.company_id and job.company_id != self.company_id:
                raise ValidationError(_('Seleccione un cargo del maestro de la empresa.'))
        else:
            candidates = jobs.search([('name', '=ilike', 'Cosechero'), ('company_id', 'in', [False, self.company_id.id])], limit=2)
            if len(candidates) > 1:
                raise ValidationError(_('Hay varios cargos Cosechero. Seleccione uno del maestro.'))
            job = candidates or jobs.create({'name': 'Cosechero', 'company_id': self.company_id.id})
        worker = employees.create({
            'name': name, 'pin': pin, 'gender': gender, 'job_id': job.id,
            'company_id': self.company_id.id, 'is_contratista': self.group_type == 'contratista',
            'contratista_id': self.partner_id.id if self.group_type == 'contratista' else False,
            'harvest_enrollment_uid': event_uid, 'harvest_enrollment_fingerprint': digest,
        })
        relation = 'contract_line' if self.group_type == 'contratista' else 'salary_line'
        self.write({relation: [Command.create({'employee_id': worker.id})]})
        self._harvest_check_worker(worker)
        return worker

    def harvest_record_attendance(self, data):
        self._harvest_check_crew()
        self.env['hr.attendance'].check_access('create')
        event_uid = str(data.get('client_uuid') or '').strip()
        entries = data.get('entries')
        if not event_uid or len(event_uid) > 100 or not isinstance(entries, list) or not 0 < len(entries) <= 500:
            raise ValidationError(_('La asistencia requiere su identificador y entre 1 y 500 trabajadores.'))
        try:
            day = fields.Date.to_date(data.get('date'))
        except (ValueError, TypeError):
            day = False
        if not day:
            raise ValidationError(_('Seleccione la fecha de asistencia.'))
        result = self.env['hr.attendance'].with_context(harvest_attendance_scope='cosecha')
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValidationError(_('La asistencia contiene un trabajador inválido.'))
            employees = self.env['hr.employee']
            if entry.get('worker_id'):
                worker = employees.browse(int(entry['worker_id'])).exists()
            else:
                worker = employees.search([('company_id', '=', self.company_id.id),
                                           ('harvest_enrollment_uid', '=', str(entry.get('worker_uuid') or ''))], limit=1)
            if not worker:
                raise ValidationError(_('Sincronice primero el enrolamiento del trabajador.'))
            self._harvest_check_worker(worker)
            if worker.id in seen:
                raise ValidationError(_('Un trabajador aparece más de una vez en la asistencia.'))
            seen.add(worker.id)
            start, end = event_time(entry.get('check_in')), event_time(entry.get('check_out'))
            if end <= start or (end - start).total_seconds() > 24 * 3600:
                raise ValidationError(_('La salida debe ser posterior a la entrada y la jornada no puede superar 24 horas.'))
            if fields.Datetime.context_timestamp(self, start).date() != day:
                raise ValidationError(_('La entrada no corresponde a la fecha de asistencia.'))
            digest = fingerprint([self.id, worker.id, str(day), start.isoformat(), end.isoformat()])
            previous = result.search([('employee_id', '=', worker.id), ('harvest_uid', '=', event_uid)], limit=1)
            if previous:
                if previous.harvest_fingerprint != digest:
                    raise ValidationError(_('Una asistencia recibida no puede reenviarse con otras horas. Corríjala en Odoo.'))
                result |= previous
            else:
                result |= result.create({
                    'employee_id': worker.id, 'check_in': start, 'check_out': end,
                    'harvest_crew_id': self.id, 'harvest_uid': event_uid, 'harvest_fingerprint': digest,
                })
        return result

