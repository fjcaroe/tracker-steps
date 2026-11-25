"""Scoped mobile enrollment and attendance using native records and permissions."""
import hmac

from odoo import fields, http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from .scope import environment_scope
from .lifecycle import LifecycleHarvestApi


class CrewHarvestApi(LifecycleHarvestApi):
    def _json(self, payload, status=200):
        if request.session.uid and 'crews' in payload:
            payload = dict(payload, crew_permissions={
                'enroll': request.env['hr.employee'].has_access('create') and request.env['hr.salary.custom'].has_access('write'),
                'attendance': request.env['hr.attendance'].has_access('create'),
            })
            payload['crew_attendance'] = []
            payload['crew_attendance_scope'] = 'cosecha'
            if request.env['hr.attendance'].has_access('read'):
                groups = {}
                for attendance in request.env['hr.attendance'].with_context(harvest_attendance_scope='cosecha').search([
                        ('harvest_crew_id.company_id', '=', request.env.company.id),
                        ('check_in', '>=', fields.Datetime.subtract(fields.Datetime.now(), days=14))]):
                    day = fields.Datetime.context_timestamp(attendance, attendance.check_in).date().isoformat()
                    key = attendance.harvest_crew_id.id, day
                    groups.setdefault(key, set()).add(attendance.employee_id.id)
                payload['crew_attendance'] = [{'crew_id': key[0], 'date': key[1], 'worker_ids': sorted(workers)}
                                              for key, workers in groups.items()]
        return super()._json(payload, status=status)

    def _reference_data(self, resource, query=None, limit=None):
        if resource == 'jobs':
            domain = [('company_id', 'in', [False, request.env.company.id])]
            if query:
                domain.append(('name', 'ilike', query))
            return [self._item(job) for job in request.env['hr.job'].search(domain, order='name,id', limit=500)]
        rows = super()._reference_data(resource, query, limit)
        if resource == 'crews':
            for row in rows:
                crew = request.env['hr.salary.custom'].browse(row['id'])
                row['worker_ids'] = crew._harvest_members().ids
        if resource == 'workers':
            for row in rows:
                employee = request.env['hr.employee'].browse(row['id'])
                row['job_id'] = employee.job_id.id or False
                row['job'] = employee.job_id.display_name or ''
        return rows

    @http.route('/api/harvest/crew/sync', type='http', auth='user', methods=['POST'], csrf=False, sitemap=False)
    def crew_sync(self, **kwargs):
        error = self._active_company()
        if error is not None:
            return error
        if not self._same_origin():
            return self._json({'ok': False, 'error': _('Origen no permitido.')}, status=403)
        payload = self._payload()
        scope = payload.get('scope')
        if not isinstance(scope, str) or not hmac.compare_digest(scope, environment_scope(request.env)):
            return self._json({'ok': False, 'error': _('La empresa o la sesión no coinciden con los pendientes.')}, status=409)
        workers, attendances = payload.get('workers', []), payload.get('attendances', [])
        if not isinstance(workers, list) or not isinstance(attendances, list) or len(workers) > 100 or len(attendances) > 31:
            return self._json({'ok': False, 'error': _('El lote de cuadrilla supera el máximo permitido.')}, status=422)
        response = {'ok': True, 'worker_results': [], 'attendance_results': []}
        for rows, key, method in ((workers, 'worker_results', 'harvest_enroll_worker'),
                                  (attendances, 'attendance_results', 'harvest_record_attendance')):
            for row in rows:
                reference = str(row.get('client_uuid') or '') if isinstance(row, dict) else ''
                try:
                    with request.env.cr.savepoint():
                        if not isinstance(row, dict):
                            raise ValidationError(_('El registro de cuadrilla no es válido.'))
                        crew = self._native_record('hr.salary.custom', row.get('crew_id'))
                        result = getattr(crew, method)(row)
                        response[key].append({'client_uuid': reference, 'ok': True,
                                              'id': result.id if method == 'harvest_enroll_worker' else result.ids})
                except (AccessError, UserError, ValidationError, ValueError, TypeError) as exc:
                    response['ok'] = False
                    response[key].append({'client_uuid': reference, 'ok': False, 'error': str(exc)})
        return self._json(response)
