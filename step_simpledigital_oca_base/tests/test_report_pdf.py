"""Real authenticated PDF route and wkhtmltopdf, using exact runtime assets."""
from contextlib import ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import re
import threading
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlencode, urljoin, urlsplit
import uuid

from lxml import html as etree
from PyPDF2 import PdfFileReader
from odoo import tools
from odoo.tests import HttpCase, tagged
from .report_fixture import StoredReportFixture


@tagged('post_install', '-at_install', 'stored_payslip_pdf')
class StoredPayslipPdfCase(StoredReportFixture, HttpCase):
    def asset_sidecar(self, documents):
        """Avoid nested test-cursor requests while wkhtmltopdf loads CSS/fonts."""
        origin = self.base_url()
        todo = []
        for document in documents:
            todo += etree.fromstring(document).xpath('//link[@href]/@href | //script[@src]/@src | //img[@src]/@src')
        scopes = {match.group(1) for link in todo
                  if (match := re.match(r'^/web/assets/([0-9]+)/[0-9a-f]+/', urlsplit(link).path))}
        for link in list(todo):
            match = re.match(r'^/web/assets/([0-9a-f]+/[^/]+)$', urlsplit(link).path)
            if match:
                todo += ['/web/assets/' + scope + '/' + match.group(1) for scope in scopes]
        cache, missing = {}, []
        while todo:
            link = todo.pop()
            if link.startswith('data:'):
                continue
            parsed = urlsplit(urljoin(origin, link))
            self.assertEqual(parsed.netloc, urlsplit(origin).netloc)
            if parsed.path in cache:
                continue
            response = self.url_open(parsed.path + ('?' + parsed.query if parsed.query else ''))
            self.assertEqual(response.status_code, 200, parsed.path)
            mime = response.headers.get('Content-Type', 'application/octet-stream')
            cache[parsed.path] = response.content, mime
            if 'text/css' in mime:
                for raw in re.findall(r'url\(\s*([^)]*?)\s*\)', response.text):
                    value = raw.strip('\"\' ')
                    if value and not value.startswith('data:'):
                        host = urlsplit(value).netloc
                        if host:
                            self.assertEqual(host, 'fonts.odoocdn.com')
                        else:
                            todo.append(urljoin(parsed.path, value))
        self.assertTrue(cache)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler):
                key = urlsplit(handler.path).path
                if key not in cache:
                    missing.append(key)
                    handler.send_error(404)
                    return
                content, mime = cache[key]
                handler.send_response(200)
                handler.send_header('Content-Type', mime)
                handler.send_header('Content-Length', str(len(content)))
                handler.end_headers()
                handler.wfile.write(content)

            def log_message(handler, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread, missing, {key: hashlib.sha256(value[0]).hexdigest() for key, value in cache.items()}

    def test_actual_employee_pdf_active_archived_and_basic_visibility(self):
        slip = self.closed_slip()
        owner = self.employee_actor()
        self.employee.user_id = owner
        password = uuid.uuid4().hex
        owner.with_context(no_reset_password=True).write({'password': password})
        self.authenticate(owner.login, password)
        self.contract.wage = 9000000
        self.env.flush_all()
        before = self.stored_snapshot(slip)
        output = Path(tools.config['data_dir']) / 'payslip-pdf-evidence'
        if not str(output.resolve()).startswith('/opt/steps-validation/'):
            self.fail('PDF evidence must remain in a private validation data directory')
        output.mkdir(exist_ok=True)
        proofs = []
        self.env['ir.config_parameter'].sudo().set_param('report.url', self.base_url())
        for archived, hide in ((False, False), (True, True)):
            self.structure.write({'active': not archived, 'hide_basic_on_pdf': hide})
            context = {'force_report_rendering': True, 'allowed_company_ids': self.company.ids}
            suffix = 'step_simpledigital_oca_base.report_payslip/%s?' % slip.id + urlencode({'context': json.dumps(context)})
            html = self.url_open('/report/html/' + suffix)
            self.assertEqual(html.status_code, 200)
            self.assertEqual('Stored BASIC' in html.text, not hide)
            self.assertIn('Stored NEGATIVE', html.text)
            self.assertIn('Stored ZERO', html.text)
            self.assertIn('Stored NULL_VALUE', html.text)
            action = self.scope.ref('payroll.action_report_payslip')
            bodies, ids, header, footer, paper = action._prepare_html(html.content, report_model='hr.payslip')
            server, thread, missing, assets = self.asset_sidecar([html.content, *bodies, header, footer])
            self.env['ir.config_parameter'].sudo().set_param('report.url', 'http://127.0.0.1:%s' % server.server_port)
            try:
                with ExitStack() as stack:
                    for method in ('compute_sheet', 'get_lines_dict', '_get_paid_amount', '_get_contract_wage', '_compute_provider_totals'):
                        stack.enter_context(patch.object(type(slip), method, side_effect=AssertionError('PDF cannot compute payroll')))
                    stack.enter_context(patch.object(type(slip.line_ids), '_compute_total', side_effect=AssertionError('PDF cannot compute salary totals')))
                    response = self.url_open('/report/pdf/' + suffix, timeout=120)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                self.env['ir.config_parameter'].sudo().set_param('report.url', self.base_url())
            self.assertFalse(missing, missing)
            self.assertEqual(response.status_code, 200)
            self.assertIn('application/pdf', response.headers.get('Content-Type', ''))
            self.assertTrue(response.content.startswith(b'%PDF-'))
            reader = PdfFileReader(io.BytesIO(response.content))
            self.assertGreater(reader.getNumPages(), 0)
            parser_path = os.environ.get('STEPS_PAYSLIP_PDF_PARSER_PATH')
            if parser_path:
                parser_path = Path(parser_path).resolve()
                self.assertTrue(parser_path.is_relative_to(Path('/opt/steps-validation')))
                if str(parser_path) not in sys.path:
                    sys.path.insert(0, str(parser_path))
            try:
                from pypdf import PdfReader
            except ImportError:
                self.fail('Install a private pypdf runtime for actual PDF text verification; PyPDF2 1.26 cannot extract this wkhtml output')
            pdf_text = '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(response.content)).pages)
            normalized = re.sub(r'\s+', ' ', pdf_text)
            self.assertTrue(normalized.strip(), 'Actual PDF text must be extractable')
            for expected in ('Stored NEGATIVE', 'Stored ZERO', 'Stored NULL_VALUE',
                             'PRIVATE/PDF/1', 'Original stored payslip name'):
                self.assertIn(expected, normalized)
            self.assertEqual('Stored BASIC' in normalized, not hide)
            self.assertEqual(self.stored_snapshot(slip), before)
            name = 'stored-%s-%s.pdf' % ('archived-hidden' if archived else 'active-basic', slip.id)
            with (output / name).open('xb') as handle:
                handle.write(response.content)
            proofs.append({'file': name, 'sha256': hashlib.sha256(response.content).hexdigest(),
                'pages': reader.getNumPages(), 'actor_id': owner.id, 'normal_employee': True,
                'archived_structure': archived, 'basic_hidden': hide, 'stored_history_unchanged': True,
                'missing_assets': missing, 'runtime_asset_sha256': assets,
                'financial_verified_html_sha256': hashlib.sha256(html.content).hexdigest(),
                'verified_pdf_text_sha256': hashlib.sha256(pdf_text.encode()).hexdigest(),
                'pdf_text_reference_labels_verified': True,
                'visual_pdf_review_required': True})
        with (output / ('proof-%s.json' % slip.id)).open('x', encoding='utf-8') as handle:
            json.dump(proofs, handle, indent=2)
