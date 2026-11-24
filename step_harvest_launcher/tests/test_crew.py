from copy import deepcopy

from odoo import Command
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
        cls.partner = cls.env['res.partner'].create({'name': 'Private Harvest contractor', 'is_company': True})
        cls.job = cls.env['hr.job'].create({'name': 'Private Harvest supervisor', 'company_id': cls.company.id})
        cls.own = cls.env['hr.salary.custom'].create({'name': 'Private Harvest own', 'group_type': 'propio', 'company_id': cls.company.id})
        cls.contractor = cls.env['hr.salary.custom'].create({'name': 'Private Harvest contractor crew', 'group_type': 'contratista', 'partner_id': cls.partner.id, 'company_id': cls.company.id})

    def enrollment(self, crew=None, uid='private-enrollment', pin='9237001'):
        return {'client_uuid': uid, 'crew_id': (crew or self.own).id, 'name': 'Private Harvest worker', 'nip': pin, 'sex': 'F', 'job_id': self.job.id}

    def attendance(self, worker, uid='private-attendance'):
        return {'client_uuid': uid, 'crew_id': self.own.id, 'date': '2026-11-24', 'entries': [
            {'worker_id': worker.id, 'check_in': '2026-11-24T08:00:00Z', 'check_out': '2026-11-24T16:00:00Z'}]}

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
        values = self.attendance(worker)
        attendance = self.own.harvest_record_attendance(values)
        self.assertEqual(attendance._name, 'hr.attendance')
        self.assertEqual(attendance.employee_id, worker)
        self.assertEqual(attendance.harvest_crew_id, self.own)
        self.assertEqual(attendance.worked_hours, 8)
        self.assertEqual(self.own.harvest_record_attendance(values), attendance)
        self.assertEqual(self.env['hr.attendance'].search_count([('harvest_uid', '=', values['client_uuid'])]), 1)

    def test_attendance_can_resolve_pending_enrollment_uuid(self):
        worker = self.own.harvest_enroll_worker(self.enrollment())
        values = self.attendance(worker); values['entries'][0].pop('worker_id'); values['entries'][0]['worker_uuid'] = 'private-enrollment'
        self.assertEqual(self.own.harvest_record_attendance(values).employee_id, worker)

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
