"""Real HTTP/PDF through a private action XMLID, never reserving original IDs."""
from contextlib import ExitStack
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
import uuid

from PyPDF2 import PdfFileReader
from odoo import tools
from odoo.tests import HttpCase, tagged

from .common import action_snapshot, prepare_ce_fixture
from .pdf_capture import capture_pdf_pipeline, write_private


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
        server, thread, missing, asset_hashes, optional_missing = StoredPayslipPdfCase.asset_sidecar(
            self, [html.content, *bodies, header, footer])
        before, identity = f.stored_snapshot(slip), action_snapshot(self.action)
        output = Path(tools.config['data_dir']) / 'original-report-pdf-evidence'
        if not str(output.resolve()).startswith('/opt/steps-validation/'):
            self.fail('Original report evidence must remain in a private validation data directory')
        write_private(output / 'preview.html', html.content)
        repetitions = []
        self.env['ir.config_parameter'].sudo().set_param('report.url', 'http://127.0.0.1:%s' % server.server_port)
        try:
            with ExitStack() as stack:
                for method in ('compute_sheet', 'get_lines_dict', '_get_paid_amount', '_get_contract_wage', '_compute_provider_totals'):
                    stack.enter_context(patch.object(type(slip), method, side_effect=AssertionError('PDF cannot calculate payroll')))
                stack.enter_context(patch.object(type(slip.line_ids), '_compute_total', side_effect=AssertionError('PDF cannot calculate totals')))
                for repetition in range(1, 4):
                    directory = output / ('repetition-%s' % repetition)
                    with capture_pdf_pipeline(self.env['ir.actions.report'], directory,
                                              f.company.name, f.company.country_id.name) as capture:
                        response = self.url_open('/report/pdf/' + suffix, timeout=120)
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.content.startswith(b'%PDF-'))
                    pages = PdfFileReader(io.BytesIO(response.content)).getNumPages()
                    self.assertGreater(pages, 0)
                    self.assertEqual(action_snapshot(self.action), identity)
                    self.assertEqual(f.structure.report_id, self.action)
                    self.assertEqual(f.stored_snapshot(slip), before)
                    filename = 'original-report-stored-%s%s.pdf' % (
                        slip.id, '' if repetition == 1 else '-repeat-%s' % repetition)
                    file = write_private(output / filename, response.content)
                    repetitions.append({
                        **file, 'pages': pages, 'pipeline': 'repetition-%s/pipeline.json' % repetition,
                        'prepared_headers': len(capture['prepare_calls']),
                        'wkhtmltopdf_runs': len(capture['run_calls']),
                        'argument_calls': len(capture['argument_calls']),
                        'company_present_in_prepared_headers': all(
                            call['company_name_present'] for call in capture['prepare_calls']),
                        'country_present_in_prepared_headers': all(
                            call['country_name_present'] for call in capture['prepare_calls']),
                        'normal_run_actor': all(call['environment']['uid'] == owner.id
                            and not call['environment']['sudo'] for call in capture['run_calls']),
                    })
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
            self.env['ir.config_parameter'].sudo().set_param('report.url', self.base_url())
        self.assertFalse(missing, missing)
        self.assertEqual(action_snapshot(self.action), identity)
        self.assertEqual(f.structure.report_id, self.action)
        self.assertEqual(f.stored_snapshot(slip), before)
        proof = {
            **{key: repetitions[0][key] for key in ('file', 'sha256', 'bytes', 'pages')},
            'actor_id': owner.id, 'normal_actor': True,
            'stored_history_unchanged': True, 'original_action_unchanged': True,
            'existing_structure_fk_unchanged': True, 'missing_assets': missing,
            'original_action_numeric_adoption': False,
            'runtime_asset_sha256': asset_hashes,
            'unused_css_prefetch_404': sorted(set(optional_missing)),
            'financial_verified_html_sha256': hashlib.sha256(html.content).hexdigest(),
            'offline_pdf_text_verification_required': True,
            'visual_pdf_review_required': True,
            'repetitions': repetitions,
            'company_name': f.company.name, 'country_name': f.company.country_id.name,
            'header_layout_accepted': False,
        }
        write_private(output / 'proof.json', json.dumps(proof, indent=2, sort_keys=True))
        for repetition in repetitions:
            self.assertEqual(repetition['prepared_headers'], 1, repetition)
            self.assertEqual(repetition['wkhtmltopdf_runs'], 1, repetition)
            self.assertEqual(repetition['argument_calls'], 1, repetition)
            self.assertTrue(repetition['company_present_in_prepared_headers'], repetition)
            self.assertTrue(repetition['country_present_in_prepared_headers'], repetition)
            self.assertTrue(repetition['normal_run_actor'], repetition)
