from copy import deepcopy
from datetime import datetime

import pytz

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class HarvestCrewCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private Harvest crew company'})
        cls.foreign = cls.env['res.company'].create({'name': 'Private Harvest foreign company'})
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id], tz='UTC'))
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Private Harvest continuous UTC hours', 'company_id': cls.company.id, 'tz': 'UTC',
            'attendance_ids': [Command.clear(), *[Command.create({
                'name': 'Private Harvest eight-hour day', 'dayofweek': str(day),
                'hour_from': 8, 'hour_to': 16,
            }) for day in range(5)]],
        })
        cls.company.resource_calendar_id = cls.calendar
        cls.partner = cls.env['res.partner'].create({'name': 'Private Harvest contractor', 'is_company': True})
        cls.job = cls.env['hr.job'].create({'name': 'Private Harvest supervisor', 'company_id': cls.company.id})
        cls.own = cls.env['hr.salary.custom'].create({'name': 'Private Harvest own', 'group_type': 'propio', 'company_id': cls.company.id})
        cls.contractor = cls.env['hr.salary.custom'].create({'name': 'Private Harvest contractor crew', 'group_type': 'contratista', 'partner_id': cls.partner.id, 'company_id': cls.company.id})

    def enrollment(self, crew=None, uid='private-enrollment', pin='9237001'):
        return {'client_uuid': uid, 'crew_id': (crew or self.own).id, 'name': 'Private Harvest worker', 'nip': pin, 'sex': 'F', 'job_id': self.job.id}

    def attendance(self, worker, uid='private-attendance'):
        return {'client_uuid': uid, 'crew_id': self.own.id, 'date': '2026-11-24', 'entries': [
            {'worker_id': worker.id, 'check_in': '2026-11-24T08:00:00Z', 'check_out': '2026-11-24T16:00:00Z'}]}

    def test_attendance_menus_open_the_native_list_before_the_record_form(self):
        list_view = self.env.ref('step_harvest_launcher.harvest_attendance_list')
        form_view = self.env.ref('step_harvest_launcher.harvest_attendance_form')
        for kind in ('own', 'contractor'):
            menu = self.env.ref('step_harvest_launcher.menu_harvest_attendance_' + kind)
            action = self.env.ref('step_harvest_launcher.harvest_attendance_' + kind)
            self.assertEqual(menu.action, action)
            self.assertEqual(action.res_model, 'hr.attendance')
            self.assertEqual(action._get_action_dict()['views'], [(list_view.id, 'list'), (form_view.id, 'form')])

    def test_enrollment_creates_native_employee_job_and_membership_once(self):
        values = self.enrollment()
        worker = self.own.harvest_enroll_worker(values)
        self.assertEqual(worker.job_id, self.job)
        self.assertEqual(worker.company_id, self.company)
        self.assertEqual(worker.gender, 'female')
        self.assertIn(worker, self.own.salary_line.employee_id)
        self.assertEqual(self.own.harvest_enroll_worker(values), worker)
        self.assertEqual(len(self.own.salary_line.filtered(lambda row: row.employee_id == worker)), 1)
        self.assertFalse(self.env['hr.contract'].search([('employee_id', '=', worker.id)]))

    def test_contractor_enrollment_keeps_native_contractor_line(self):
        worker = self.contractor.harvest_enroll_worker(self.enrollment(self.contractor))
        self.assertEqual(worker.contratista_id, self.partner)
        self.assertTrue(worker.is_contratista)
        self.assertIn(worker, self.contractor.contract_line.employee_id)
        self.assertNotIn(worker, self.contractor.salary_line.employee_id)

    def test_existing_pin_and_changed_retry_are_rejected(self):
        values = self.enrollment()
        worker = self.own.harvest_enroll_worker(values)
        for changes in ({'client_uuid': 'another-request'}, {'name': 'Altered identity'}):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.own.harvest_enroll_worker(dict(values, **changes))
        self.assertEqual(worker.name, values['name'])

    def test_default_job_reuses_or_creates_native_cosechero(self):
        values = self.enrollment(); values['job_id'] = None
        worker = self.own.harvest_enroll_worker(values)
        self.assertEqual(worker.job_id.name, 'Cosechero')
        other = self.own.harvest_enroll_worker(dict(values, client_uuid='another-worker', nip='9237002'))
        self.assertEqual(worker.job_id, other.job_id)

    def test_foreign_job_and_crew_are_rejected(self):
        job = self.env['hr.job'].with_company(self.foreign).create({'name': 'Private foreign job', 'company_id': self.foreign.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.own.harvest_enroll_worker(dict(self.enrollment(), job_id=job.id))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.own.with_company(self.foreign).harvest_enroll_worker(self.enrollment())

    def test_attendance_uses_native_table_and_is_idempotent(self):
        worker = self.own.harvest_enroll_worker(self.enrollment())
        self.assertEqual(worker.resource_calendar_id, self.calendar)
        values = self.attendance(worker)
        attendance = self.own.harvest_record_attendance(values)
        self.assertEqual(attendance._name, 'hr.attendance')
        self.assertEqual(attendance.employee_id, worker)
        self.assertEqual(attendance.harvest_crew_id, self.own)
        self.assertEqual(attendance.worked_hours, 8)
        self.assertEqual(self.own.harvest_record_attendance(values), attendance)
        self.assertEqual(self.env['hr.attendance'].with_context(harvest_attendance_scope='cosecha').search_count([
            ('harvest_uid', '=', values['client_uuid'])]), 1)
        self.assertEqual(self.env['hr.attendance'].search_count([('id', '=', attendance.id)]), 0)

    def test_cosecha_attendance_is_separate_from_hr_searches_and_groups(self):
        worker = self.own.harvest_enroll_worker(self.enrollment())
        native = self.env['hr.attendance'].create({
            'employee_id': worker.id, 'check_in': '2026-11-24 08:00:00', 'check_out': '2026-11-24 16:00:00',
        })
        harvest = self.own.harvest_record_attendance(self.attendance(worker))
        domain = [('employee_id', '=', worker.id)]
        self.assertEqual(self.env['hr.attendance'].search(domain), native)
        self.assertEqual(self.env['hr.attendance'].with_context(harvest_attendance_scope='cosecha').search(domain), harvest)
        groups = self.env['hr.attendance']._read_group(domain, aggregates=['id:recordset'])
        self.assertEqual(groups[0][0], native)
        self.assertEqual(harvest.worked_hours, 8)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            harvest.write({'harvest_crew_id': False})

    def test_cosecha_does_not_change_existing_hr_overtime_on_the_same_day(self):
        worker = self.own.harvest_enroll_worker(self.enrollment())
        native = self.env['hr.attendance'].create({
            'employee_id': worker.id, 'check_in': '2026-11-24 08:00:00', 'check_out': '2026-11-24 18:00:00',
        })
        self.assertEqual(native.overtime_hours, 2)
        overtime = self.env['hr.attendance.overtime'].search([('employee_id', '=', worker.id)])
        before = overtime.read(['id', 'date', 'duration', 'duration_real'])
        harvest = self.own.harvest_record_attendance(self.attendance(worker))
        harvest.write({'check_out': '2026-11-24 20:00:00'})
        native._compute_overtime_hours()
        self.assertEqual(native.overtime_hours, 2)
        self.assertEqual(harvest.overtime_hours, 0)
        self.assertEqual(overtime.read(['id', 'date', 'duration', 'duration_real']), before)
        self.assertEqual(self.env['hr.attendance.overtime'].search([('employee_id', '=', worker.id)]), overtime)

    def test_cosecha_does_not_feed_immediate_or_regenerated_work_entries(self):
        worker = self.own.harvest_enroll_worker(self.enrollment())
        kind = self.env['hr.payroll.structure.type'].create({'name': 'Private Cosecha isolation type'})
        if 'default_work_entry_type_id' in kind._fields:
            kind.default_work_entry_type_id = self.env.ref('hr_work_entry.work_entry_type_attendance')
        contract = self.env['hr.contract'].create({
            'name': 'Private Cosecha isolation contract', 'employee_id': worker.id,
            'company_id': self.company.id, 'resource_calendar_id': self.calendar.id,
            'date_start': '2026-11-01', 'date_end': '2026-11-30', 'state': 'open', 'wage': 1000000,
            'structure_type_id': kind.id, 'work_entry_source': 'attendance',
            'date_generated_from': '2026-11-01 00:00:00', 'date_generated_to': '2026-11-30 23:59:59',
        })
        entries = self.env['hr.work.entry'].search([('employee_id', '=', worker.id)])
        before = entries.read(['id', 'active', 'date_start', 'date_stop', 'attendance_id'])
        harvest = self.own.harvest_record_attendance(self.attendance(worker))
        self.assertEqual(entries.read(['id', 'active', 'date_start', 'date_stop', 'attendance_id']), before)
        self.assertEqual(self.env['hr.work.entry'].search([('employee_id', '=', worker.id)]), entries)
        start, end = datetime(2026, 11, 24, tzinfo=pytz.UTC), datetime(2026, 11, 25, tzinfo=pytz.UTC)
        values = contract._get_work_entries_values(start, end)
        self.assertFalse(any(row.get('attendance_id') == harvest.id for row in values))
        native = self.env['hr.attendance'].create({
            'employee_id': worker.id, 'check_in': '2026-11-24 08:00:00', 'check_out': '2026-11-24 16:00:00',
        })
        values = contract._get_work_entries_values(start, end)
        self.assertTrue(any(row.get('attendance_id') == native.id for row in values))
        self.assertFalse(any(row.get('attendance_id') == harvest.id for row in values))
        self.assertTrue(self.env['hr.work.entry'].search([('attendance_id', '=', native.id)]))

    def test_attendance_can_resolve_pending_enrollment_uuid(self):
        worker = self.own.harvest_enroll_worker(self.enrollment())
        values = self.attendance(worker); values['entries'][0].pop('worker_id'); values['entries'][0]['worker_uuid'] = 'private-enrollment'
        self.assertEqual(self.own.harvest_record_attendance(values).employee_id, worker)

    def test_attendance_keeps_the_native_calendar_lunch_deduction(self):
        calendar = self.calendar.copy({
            'name': 'Private Harvest UTC hours with lunch',
            'attendance_ids': [Command.clear(), *[Command.create({
                'name': 'Private Harvest ' + period, 'dayofweek': str(day),
                'day_period': period, 'hour_from': start, 'hour_to': end,
            }) for day in range(5) for period, start, end in (
                ('morning', 8, 12), ('lunch', 12, 13), ('afternoon', 13, 16))]],
        })
        worker = self.own.harvest_enroll_worker(self.enrollment())
        worker.resource_calendar_id = calendar
        attendance = self.own.harvest_record_attendance(self.attendance(worker))
        self.assertEqual(fields.Datetime.to_string(attendance.check_in), '2026-11-24 08:00:00')
        self.assertEqual(fields.Datetime.to_string(attendance.check_out), '2026-11-24 16:00:00')
        self.assertEqual(attendance.worked_hours, 7)
        self.assertEqual(self.company.resource_calendar_id, self.calendar)

    def test_attendance_rejects_invalid_or_changed_hours(self):
        worker = self.own.harvest_enroll_worker(self.enrollment())
        values = self.attendance(worker)
        attendance = self.own.harvest_record_attendance(values)
        for changes in ({'check_out': '2026-11-24T07:00:00Z'}, {'check_out': '2026-11-24T17:00:00Z'}, {'check_in': '2026-11-25T08:00:00Z'}, {'check_in': '2026-11-24T08:00:00'}):
            invalid = deepcopy(values); invalid['entries'][0].update(changes)
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.own.harvest_record_attendance(invalid)
        self.assertEqual(attendance.check_out.hour, 16)

    def test_enrollment_and_attendance_respect_native_user_permissions(self):
        worker = self.own.harvest_enroll_worker(self.enrollment())
        user = new_test_user(self.env, login='private_harvest_no_hr',
                             company_id=self.company.id, company_ids=[Command.set(self.company.ids)], groups='base.group_user')
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.own.with_user(user).harvest_enroll_worker(dict(self.enrollment(), client_uuid='no-access', nip='9237003'))
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.own.with_user(user).harvest_record_attendance(self.attendance(worker))
