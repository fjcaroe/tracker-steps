"""Allocate a crew day on native OTs and feed the existing costing lines."""
import math
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class HarvestWorkHours(models.Model):
    _inherit = 'step.cosecha.registry'

    mobile_hours_required = fields.Boolean(string='Cierre con horas de trabajo', copy=False)
    mobile_work_start = fields.Datetime(string='Inicio de trabajo', readonly=True, copy=False)
    mobile_work_end = fields.Datetime(string='Fin de trabajo', readonly=True, copy=False)
    mobile_work_hours = fields.Float(string='Horas trabajadas por persona', readonly=True, copy=False)
    mobile_work_day = fields.Date(string='Día de jornada', readonly=True, copy=False, index=True)
    mobile_day_hours = fields.Float(string='Horas de jornada', readonly=True, copy=False)
    mobile_last_order = fields.Boolean(string='Última OT del día', readonly=True, copy=False)

    def _harvest_day_orders(self, day, lock=False):
        self.ensure_one()
        crew = self.salary_id_contrac if self.type_tarea == 'contratista' else self.salary_id
        if not crew:
            raise ValidationError(_('Asigne una cuadrilla nativa a la OT antes de registrar sus horas.'))
        crew._harvest_check_crew()
        if lock:
            # All OTs of this crew serialize on the same native row, including
            # the first two closures of a day when no allocation exists yet.
            self.env.cr.execute('SELECT id FROM hr_salary_custom WHERE id=%s FOR UPDATE', [crew.id])
        domain = [('company_id', '=', self.company_id.id), ('type_tarea', '=', self.type_tarea),
                  ('salary_id_contrac' if self.type_tarea == 'contratista' else 'salary_id', '=', crew.id),
                  ('mobile_work_day', '=', day), ('mobile_work_start', '!=', False),
                  ('mobile_status', 'in', ['closed', 'reviewed', 'sent']), ('id', '!=', self._origin.id or 0)]
        # Allocation is an invariant across all users, even when record rules
        # hide another supervisor's OT. Return only aggregate hours to the app.
        return self.sudo().search(domain), crew

    def _harvest_hours_summary(self, day):
        orders, crew = self._harvest_day_orders(day)
        target = orders[0].mobile_day_hours if orders else self.company_id.harvest_hours_per_day
        assigned = sum(orders.mapped('mobile_work_hours'))
        return {'day': str(day), 'day_hours': target, 'assigned_hours': assigned,
                'remaining_hours': round(max(0, target - assigned), 4),
                'day_closed': any(orders.mapped('mobile_last_order')),
                'crew_id': crew.id}

    def _harvest_apply_work_hours(self, values):
        self.ensure_one()
        if not isinstance(values, dict):
            raise ValidationError(_('Indique inicio, fin y horas trabajadas para cerrar la OT.'))
        try:
            start = datetime.fromisoformat(values['start'].replace('Z', '+00:00'))
            end = datetime.fromisoformat(values['end'].replace('Z', '+00:00'))
            hours = values['hours']
            if start.tzinfo is None or end.tzinfo is None or type(hours) not in (int, float):
                raise ValueError()
            start, end = (value.astimezone(timezone.utc).replace(tzinfo=None) for value in (start, end))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise ValidationError(_('Indique fechas con zona horaria y horas válidas.'))
        elapsed = (end - start).total_seconds() / 3600
        if not math.isfinite(hours) or not 0 < hours <= 24 or not 0 < elapsed <= 24 or hours > elapsed + 0.0001:
            raise ValidationError(_('Las horas deben ser positivas, no superar el intervalo ni 24 horas.'))
        day = fields.Datetime.context_timestamp(self, start).date()
        if self.date and day != fields.Datetime.context_timestamp(self, self.date).date():
            raise ValidationError(_('El inicio debe corresponder al día de la OT.'))
        last = values.get('last_order') is True
        if self.mobile_status != 'progress':
            if (self.mobile_work_start, self.mobile_work_end, self.mobile_work_hours, self.mobile_last_order) != (start, end, hours, last):
                raise ValidationError(_('Una OT cerrada conserva sus horas. Reábrala antes de corregirlas.'))
            return
        if self.state != 'in' or self.invoice_id or self.purchase_id:
            raise ValidationError(_('La OT debe estar en Ingresado y sin documentos de costo para asignar sus horas.'))
        orders, crew = self._harvest_day_orders(day, lock=True)
        if any(orders.mapped('mobile_last_order')):
            raise ValidationError(_('La jornada ya está cuadrada. Reabra primero la última OT del día.'))
        if any(start < row.mobile_work_end and end > row.mobile_work_start for row in orders):
            raise ValidationError(_('El horario se superpone con otra OT de esta cuadrilla.'))
        target = orders[0].mobile_day_hours if orders else self.company_id.harvest_hours_per_day
        assigned = sum(orders.mapped('mobile_work_hours'))
        if assigned + hours > target + 0.0001:
            raise ValidationError(_('Las OT superan las horas de jornada configuradas para esta empresa.'))
        if last and abs(assigned + hours - target) > 0.0001:
            raise ValidationError(_('La última OT debe completar el 100%% de la jornada: faltan %.2f horas.') % (target - assigned))
        if last and self.sudo().search_count([
                ('company_id', '=', self.company_id.id),
                ('salary_id_contrac' if self.type_tarea == 'contratista' else 'salary_id', '=', crew.id),
                ('mobile_status', '=', 'progress'), ('id', '!=', self.id),
                ('date', '>=', self._harvest_day_bounds(day)[0]), ('date', '<', self._harvest_day_bounds(day)[1])]):
            raise ValidationError(_('Cierre primero las otras OT abiertas de esta cuadrilla en el día.'))
        self._harvest_cost_hours(crew, day, hours)
        self._harvest_write({'mobile_work_start': start, 'mobile_work_end': end, 'mobile_work_hours': hours,
                             'mobile_work_day': day, 'mobile_day_hours': target, 'mobile_last_order': last})

    def _harvest_day_bounds(self, day):
        tz = ZoneInfo(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        return tuple(datetime.combine(value, time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
                     for value in (day, day + timedelta(days=1)))

    def _harvest_cost_hours(self, crew, day, hours):
        first, end = self._harvest_day_bounds(day)
        attendance = self.env['hr.attendance'].with_context(harvest_attendance_scope='cosecha').search([
            ('harvest_crew_id', '=', crew.id), ('check_in', '>=', first), ('check_in', '<', end)])
        employees = attendance.employee_id if attendance else crew._harvest_members()
        employees |= self.tarja_registry_line.employee_id
        if not employees:
            raise ValidationError(_('Registre los integrantes o la asistencia de la cuadrilla antes de cerrar.'))
        lines = self.registry_line if self.type_tarea == 'propio' else self.registry_tarja_line
        employees |= lines.employee_id
        model = lines.browse()
        for worker in employees:
            crew._harvest_check_worker(worker)
            existing = lines.filtered(lambda row: row.employee_id == worker)
            if len(existing) > 1 or existing and (existing.hrs not in (0, self.mobile_work_hours) or
                    'hrs_extra' in existing._fields and existing.hrs_extra):
                raise ValidationError(_('La OT tiene horas editadas en Cosecha. Revise sus líneas antes de reemplazarlas.'))
            if existing:
                existing.write({'hrs': hours})
            else:
                values = {'registry_id': self.id, 'employee_id': worker.id, 'hrs': hours,
                          'cost_id': self.cost_id.id, 'labor_id': self.labor_id.id}
                if self.type_tarea == 'propio':
                    contract = self.env['hr.contract'].search([
                        ('employee_id', '=', worker.id), ('company_id', '=', self.company_id.id),
                        ('date_start', '<=', day), '|', ('date_end', '=', False), ('date_end', '>=', day)],
                        order='date_start desc,id desc', limit=1)
                    values['contract_id'] = contract.id
                model.create(values)

    def _harvest_check_reopen_hours(self):
        if self.mobile_work_day:
            orders, crew = self._harvest_day_orders(self.mobile_work_day, lock=True)
            if any(orders.mapped('mobile_last_order')):
                raise ValidationError(_('Reabra primero la última OT para corregir la distribución de jornada.'))
