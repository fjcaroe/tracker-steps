"""Real HTTP/PDF through a private action XMLID, never reserving original IDs."""
from contextlib import ExitStack
import io
import json
from unittest.mock import patch
from urllib.parse import urlencode
import uuid

from PyPDF2 import PdfFileReader
from odoo.tests import HttpCase, tagged

from .common import action_snapshot, prepare_ce_fixture


@tagged('post_install', '-at_install', 'original_report_pdf')
class OriginalPayrollReportPdfCase(HttpCase):
    def setUp(self):
        super().setUp()
        self.fixture, self.action = prepare_ce_fixture(self)

    def test_real_private_original_action_pdf_prints_stored_history_without_action_edits(self):
        f = self.fixture
        slip = f.closed_slip()
        f.structure.active = False
        owner = f.employee_actor()
        f.employee.user_id = owner
        password = uuid.uuid4().hex
        owner.with_context(no_reset_password=True).write({'password': password})
        self.authenticate(owner.login, password)
        xmlname = 'private_original_report_pdf_%s' % self.action.id
        self.env['ir.model.data'].create({'module': 'step_payroll_original_report', 'name': xmlname,
            'model': 'ir.actions.report', 'res_id': self.action.id, 'noupdate': False})
        suffix = 'step_payroll_original_report.%s/%s?' % (xmlname, slip.id) + urlencode({'context': json.dumps({
            'force_report_rendering': True, 'allowed_company_ids': f.company.ids})})
        self.env['ir.config_parameter'].sudo().set_param('report.url', self.base_url())
        html = self.url_open('/report/html/' + suffix)
        self.assertEqual(html.status_code, 200)
        for literal in ('Stored ZERO', 'Stored NEGATIVE', 'Stored NULL_VALUE', 'PRIVATE/PDF/1'):
            self.assertIn(literal, html.text)
        bodies, ids, header, footer, paper = self.action._prepare_html(html.content, report_model='hr.payslip')
        # This existing accepted sidecar only serves actual fetched runtime
        # assets; it fabricates no CSS, images, salary values or PDF bytes.
        from odoo.addons.step_simpledigital_oca_base.tests.test_report_pdf import StoredPayslipPdfCase
        server, thread, missing, unused_hashes, unused_optional = StoredPayslipPdfCase.asset_sidecar(
            self, [html.content, *bodies, header, footer])
        before, identity = f.stored_snapshot(slip), action_snapshot(self.action)
        self.env['ir.config_parameter'].sudo().set_param('report.url', 'http://127.0.0.1:%s' % server.server_port)
        try:
            with ExitStack() as stack:
                for method in ('compute_sheet', 'get_lines_dict', '_get_paid_amount', '_get_contract_wage', '_compute_provider_totals'):
                    stack.enter_context(patch.object(type(slip), method, side_effect=AssertionError('PDF cannot calculate payroll')))
                stack.enter_context(patch.object(type(slip.line_ids), '_compute_total', side_effect=AssertionError('PDF cannot calculate totals')))
                response = self.url_open('/report/pdf/' + suffix, timeout=120)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
            self.env['ir.config_parameter'].sudo().set_param('report.url', self.base_url())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertGreater(PdfFileReader(io.BytesIO(response.content)).getNumPages(), 0)
        self.assertFalse(missing, missing)
        self.assertEqual(action_snapshot(self.action), identity)
        self.assertEqual(f.structure.report_id, self.action)
        self.assertEqual(f.stored_snapshot(slip), before)
