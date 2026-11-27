"""Keep SyS payroll's weekly-hours field on the original resource calendar."""
from odoo import api, fields, models


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    hours_per_week = fields.Float('Hours per Week', compute='_compute_sys_hours_per_week',
                                  store=True, readonly=True, copy=False)

    @api.depends('attendance_ids.hour_from', 'attendance_ids.hour_to', 'attendance_ids.work_entry_type_id.is_leave')
    def _compute_sys_hours_per_week(self):
        for calendar in self:
            attendances = calendar.attendance_ids.filtered(lambda row: not row.work_entry_type_id.is_leave)
            hours = sum(attendances.mapped('duration_hours'))
            calendar.hours_per_week = hours / (2 if calendar.two_weeks_calendar else 1)
