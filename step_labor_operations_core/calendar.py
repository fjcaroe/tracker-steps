"""Operational weekly hours without depending on Payroll's calendar extension."""


def weekly_hours(calendar):
    calendar.ensure_one()
    # Existing destinations keep their effective historical payroll input.
    if 'hours_per_week' in calendar._fields:
        return calendar.hours_per_week
    if calendar.flexible_hours:
        return calendar.full_time_required_hours
    attendance = calendar.attendance_ids.filtered(
        lambda line: not line.display_type and not line.resource_id and line.day_period != 'lunch')
    hours = sum(line.hour_to - line.hour_from for line in attendance)
    return hours / 2 if calendar.two_weeks_calendar else hours
