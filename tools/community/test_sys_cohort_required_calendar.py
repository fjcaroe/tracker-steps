import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sys_cohort_required import COLUMNS, guard


class CalendarAdmission(unittest.TestCase):
    def setUp(self):
        self.cr = SimpleNamespace(dbname='COMMUNITY_SYS_PREVIRED_COHORT_TEST')
        self.ids = {'.'.join(key): i for i, key in enumerate(COLUMNS, 1)}
        self.field = 'resource_calendar.previred_workday_type'
        self.ids[self.field] = 28900
        self.drop = Mock()

    def test_old_and_current_plans_preserve_the_original_field(self):
        for plan in (self.ids, {k: v for k, v in self.ids.items() if k != self.field}):
            checked = guard(self.drop, self.cr.dbname, plan)
            with patch('sys_cohort_required.read_original', return_value=28900) as read:
                checked(self.cr, 'resource_calendar', 'previred_workday_type')
                read.assert_called_once_with(self.cr, 'resource_calendar', 'previred_workday_type')
            with patch('sys_cohort_required.read_original', return_value=42), self.assertRaises(ValueError):
                checked(self.cr, 'resource_calendar', 'previred_workday_type')
        self.drop.assert_not_called()

    def test_unrelated_fields_and_foreign_database_keep_the_original_handler(self):
        checked = guard(self.drop, self.cr.dbname, self.ids)
        checked(self.cr, 'resource_calendar', 'unrelated')
        checked(SimpleNamespace(dbname='different'), 'resource_calendar', 'previred_workday_type')
        self.assertEqual(self.drop.call_count, 2)

    def test_incomplete_original_inventory_is_rejected(self):
        values = dict(self.ids)
        del values['hr_payslip.name']
        with self.assertRaises(ValueError):
            guard(self.drop, self.cr.dbname, values)
