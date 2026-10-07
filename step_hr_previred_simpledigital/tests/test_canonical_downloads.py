"""Exercise the legacy HTTP links against the actual canonical extractor."""
from unittest.mock import patch
from odoo.http import request
from odoo.tests.common import HttpCase, new_test_user, tagged
from odoo.addons.step_hr_previred.tests.common import PreviredCase, make_row
from odoo.addons.step_hr_previred.tools import previred
from odoo.addons.l10n_cl_simpledigital_payroll.controllers.previred_txt import PreviredExportController


@tagged('post_install', '-at_install')
class TestCanonicalDownloads(PreviredCase, HttpCase):
    def test_legacy_txt_and_csv_apply_allowance_and_fraction_corrections(self):
        employee = self.make_employee('Canonical download fixture', '18656818-4', self.dep_admin)
        slip = self.make_payslip(employee, self.dep_admin)
        slip.worked_days_line_ids.unlink()
        attendance = self.env.ref('hr_work_entry.work_entry_type_attendance')
        self.env['hr.payslip.worked_days'].create({
            'name': 'Asistencia', 'payslip_id': slip.id,
            'work_entry_type_id': attendance.id, 'number_of_days': 29.65,
            'number_of_hours': 237.2,
        })
        new_test_user(self.env, login='canonical_exporter', password='canonical_exporter',
                      company_id=self.company.id, company_ids=[(6, 0, self.company.ids)],
                      groups='hr_payroll.group_hr_payroll_manager,step_hr_previred.group_previred_generate')
        self.authenticate('canonical_exporter', 'canonical_exporter')
        cases = [(make_row(rut='18656818', dv='4', overrides={22:'13870', 83:'0'}), '0', '0', '13870'),
                 (make_row(rut='18656818', dv='4', overrides={22:'-6936', 83:'5'}), '0', '6936', '0')]
        for raw, allowance, refund, ips in cases:
            def raw_response(controller, **kwargs):
                return request.make_response(previred.txt_bytes(';'.join(raw) + '\r\n'))
            with patch.object(PreviredExportController, 'download_previred_txt', raw_response):
                for ext in ('txt', 'csv'):
                    response = self.url_open('/hr_payroll/previred/%s?period=082026&company_id=%s' % (ext, self.company.id))
                    self.assertEqual(response.status_code, 200, response.text[:1000])
                    rows = [line.split(';') for line in response.text.strip().splitlines()]
                    self.assertEqual(len(rows), 1, response.text[:1000])
                    self.assertEqual(len(rows[0]), 105)
                    self.assertEqual(rows[0][12], '30')
                    self.assertEqual(rows[0][21], allowance)
                    self.assertEqual(rows[0][23], refund)
                    self.assertEqual(rows[0][72], ips)
        self.assertEqual(slip.worked_days_line_ids.number_of_days, 29.65)

    def test_rut_views_follow_employee_master(self):
        employee = self.make_employee('RUT fixture', '18656818-4', self.dep_admin)
        slip = self.make_payslip(employee, self.dep_admin)
        self.assertEqual(slip.step_employee_rut, employee.identification_id)
        self.assertEqual(slip.contract_id.step_employee_rut, employee.identification_id)
        employee.identification_id = '13789922-1'
        self.assertEqual(slip.step_employee_rut, employee.identification_id)
        self.assertEqual(slip.contract_id.step_employee_rut, employee.identification_id)

