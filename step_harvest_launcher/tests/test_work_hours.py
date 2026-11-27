from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class HarvestWorkHoursCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private OT hours', 'harvest_hours_per_day': 8})
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids, tz='UTC'))
        cls.worker = cls.env['hr.employee'].create({'name': 'Private OT worker', 'company_id': cls.company.id})
        cls.crew = cls.env['hr.salary.custom'].create({'name': 'Private OT crew', 'company_id': cls.company.id,
            'group_type': 'propio', 'salary_line': [Command.create({'employee_id': cls.worker.id})]})

    def order(self, name='Private OT'):
        return self.env['step.cosecha.registry'].create({'name': name, 'mobile_work_order': name,
            'company_id': self.company.id, 'type_tarea': 'propio', 'salary_id': self.crew.id,
            'product_uom_id': self.env.ref('uom.product_uom_kgm').id, 'date': '2026-11-27 08:00:00',
            'mobile_hours_required': True})

    def close(self, order, start=8, end=12, hours=4, last=False):
        return order._harvest_transition('close', [], {'start': f'2026-11-27T{start:02}:00:00Z',
            'end': f'2026-11-27T{end:02}:00:00Z', 'hours': hours, 'last_order': last})

    def test_split_day_feeds_native_cost_lines_and_retry_is_idempotent(self):
        first = self.order()
        self.close(first, hours=3)
        second = self.order('Private final OT')
        self.assertEqual(second._harvest_hours_summary('2026-11-27')['remaining_hours'], 5)
        self.close(second, start=12, end=18, hours=5, last=True)
        self.assertEqual(first.registry_line.hrs + second.registry_line.hrs, 8)
        self.assertEqual(first.registry_line.employee_id, self.worker)
        self.close(second, start=12, end=18, hours=5, last=True)
        self.assertEqual(len(second.registry_line), 1)
        self.assertEqual(second.mobile_status, 'closed')
        with self.assertRaises(ValidationError):
            self.close(second, start=12, end=18, hours=4, last=True)

    def test_last_order_must_balance_and_no_more_closures_follow_it(self):
        first = self.order()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.close(first, last=True)
        self.close(first, end=16, hours=8, last=True)
        extra = self.order('Private extra OT')
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.close(extra, start=17, end=18, hours=1)

    def test_overlap_overflow_and_impossible_duration_are_rejected(self):
        first = self.order()
        self.close(first, end=13, hours=5)
        second = self.order('Private second OT')
        for args in ({'start': 12, 'end': 15, 'hours': 3}, {'start': 13, 'end': 18, 'hours': 4},
                     {'start': 13, 'end': 14, 'hours': 2}, {'hours': float('nan')}, {'hours': -1}):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.close(second, **args)
        self.assertFalse(second.registry_line)
        self.assertEqual(second.mobile_status, 'progress')

    def test_reopen_final_before_changing_an_earlier_allocation(self):
        first = self.order()
        self.close(first)
        last = self.order('Private final OT')
        self.close(last, start=12, end=16, hours=4, last=True)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            first._harvest_transition('reopen', [])
        last._harvest_transition('reopen', [])
        first._harvest_transition('reopen', [])
        self.close(first, hours=3)
        self.close(last, start=12, end=18, hours=5, last=True)
        self.assertEqual(first.registry_line.hrs + last.registry_line.hrs, 8)

    def test_config_snapshot_preserves_started_day_and_manual_cost_hours(self):
        first = self.order()
        self.close(first)
        self.company.harvest_hours_per_day = 7
        second = self.order('Private second OT')
        self.assertEqual(second._harvest_hours_summary('2026-11-27')['day_hours'], 8)
        second.registry_line = [Command.create({'employee_id': self.worker.id, 'hrs': 1.5})]
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.close(second, start=12, end=16, hours=4, last=True)
        self.assertEqual(second.registry_line.hrs, 1.5)

    def test_other_open_ot_blocks_final_closure_and_missing_hours_fail(self):
        first, other = self.order(), self.order('Private open OT')
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.close(first, end=16, hours=8, last=True)
        with self.assertRaises(ValidationError):
            first._harvest_transition('close', [])
        self.assertEqual(other.mobile_status, 'progress')

    def test_closed_hours_are_not_public_write_fields(self):
        first = self.order()
        with self.assertRaises(AccessError):
            first.with_user(self.env.ref('base.user_admin')).write({'mobile_work_hours': 3})
