from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "hr_consumers")
class TestContractWeeklyHours(TransactionCase):
    def calendar(self, *, two_weeks=False):
        rows = [Command.clear()]
        for week in (("0", "1") if two_weeks else (False,)):
            hours = 6 if week == "1" else 7.5
            for day in range(5):
                rows.append(Command.create({"name": "Private contractual work", "dayofweek": str(day),
                    "hour_from": 8, "hour_to": 8 + hours, "day_period": "morning", "week_type": week}))
                rows.append(Command.create({"name": "Private contractual lunch", "dayofweek": str(day),
                    "hour_from": 16, "hour_to": 17, "day_period": "lunch", "week_type": week}))
        return self.env["resource.calendar"].create({"name": "Private real weekly calendar",
            "two_weeks_calendar": two_weeks, "attendance_ids": rows})

    def test_fractional_work_week_uses_real_global_attendance_without_lunch(self):
        calendar = self.calendar()
        original = calendar.attendance_ids.read(["id", "hour_from", "hour_to", "day_period"])
        self.assertEqual(sum(calendar._get_global_attendances().mapped("duration_hours")), 37.5)
        self.assertEqual(calendar._steps_contract_weekly_hours(), 37.5)
        if "hours_per_week" in calendar._fields:
            self.assertEqual(calendar._steps_contract_weekly_hours(), calendar.hours_per_week)
        self.assertEqual(calendar.attendance_ids.read(["id", "hour_from", "hour_to", "day_period"]), original)

    def test_two_week_cycle_uses_actual_average_and_native_reference(self):
        calendar = self.calendar(two_weeks=True)
        self.assertEqual(calendar._steps_contract_weekly_hours(), 33.75)
        if "hours_per_week" in calendar._fields:
            self.assertEqual(calendar._steps_contract_weekly_hours(), calendar.hours_per_week)

    def test_dated_and_resource_specific_schedule_require_contractual_review(self):
        calendar = self.calendar()
        row = calendar._get_global_attendances()[:1]
        row.date_from = date(2026, 10, 1)
        with self.assertRaises(UserError):
            calendar._steps_contract_weekly_hours()
        row.date_from = False
        resource = self.env["resource.resource"].create({"name": "Private individual schedule resource"})
        row.resource_id = resource
        with self.assertRaises(UserError):
            calendar._steps_contract_weekly_hours()

    def test_flexible_schedule_keeps_native_value_or_requires_original_reference(self):
        calendar = self.calendar()
        calendar.flexible_hours = True
        calendar.full_time_required_hours = 42
        if "hours_per_week" in calendar._fields:
            self.assertEqual(calendar._steps_contract_weekly_hours(), calendar.hours_per_week)
        else:
            with self.assertRaises(UserError):
                calendar._steps_contract_weekly_hours()

    def test_two_week_schedule_cannot_hide_an_unassigned_original_week(self):
        calendar = self.calendar(two_weeks=True)
        calendar._get_global_attendances()[:1].week_type = False
        with self.assertRaises(UserError):
            calendar._steps_contract_weekly_hours()
