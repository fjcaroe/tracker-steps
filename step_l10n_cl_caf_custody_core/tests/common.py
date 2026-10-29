import base64
from contextlib import contextmanager
import hashlib
import json

from cryptography.hazmat.primitives.asymmetric import rsa
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.http import Request, _request_stack
from odoo.tests.common import new_test_user
from odoo.addons.step_l10n_cl_edi_core.tests.caf_cases import CAFCaseMixin
from werkzeug.wrappers import Request as WerkzeugRequest


@contextmanager
def real_request_context(env):
    """Bind a real request to the existing private transaction, no HTTP mock.

    Stream/filestore implementations stay real. Avoid Request._post_init(),
    which would discover/open sessions/databases unrelated to this test cursor.
    """
    request = Request(WerkzeugRequest.from_values('/steps/caf/custody/test/download'))
    request.db = env.cr.dbname
    request.registry = env.registry
    request.env = env
    _request_stack.push(request)
    try:
        yield request
    finally:
        assert _request_stack.pop() is request


class CAFCustodyAssertions:
    native_reference = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.issuer_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        cls.original = CAFCaseMixin.fixture(cls, private=True, pretty=True)
        cls.company = cls.env['res.company'].create({
            'name': 'SYNTHETIC CAF custody reference', 'vat': '76086428-5',
            'country_id': cls.env.ref('base.cl').id})
        cls.other_company = cls.env['res.company'].create({
            'name': 'SYNTHETIC other CAF company', 'vat': '11111111-1',
            'country_id': cls.env.ref('base.cl').id})
        suffix = 'native' if cls.native_reference else 'community'
        cls.manager = new_test_user(cls.env, login='caf_custody_manager_' + suffix,
            groups='account.group_account_manager', company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id, cls.other_company.id])])
        cls.stock_manager = new_test_user(cls.env, login='caf_custody_stock_' + suffix,
            groups='stock.group_stock_manager', company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])])
        cls.employee = new_test_user(cls.env, login='caf_custody_employee_' + suffix,
            groups='base.group_user', company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])])
        cls.document = cls.env['l10n_latam.document.type'].search([
            ('country_id.code', '=', 'CL'), ('code', '=', '33')])
        assert len(cls.document) == 1, 'Requires the original Chilean document-type master'

    def manager_model(self):
        return self.env['l10n_cl.dte.caf'].with_user(self.manager).with_context(
            allowed_company_ids=[self.company.id])

    def custody_record(self):
        values = dict(filename='SYNTHETIC_NOT_SII_CAF.xml', company_id=self.company.id,
            l10n_latam_document_type_id=self.document.id, start_nb=50, final_nb=101,
            issued_date=fields.Date.to_date('2026-10-01'))
        if not self.native_reference:
            return self.manager_model().create(dict(values, caf_file=base64.b64encode(self.original)))
        # Seed the actual native table without executing/copying its upload or
        # consuming its PostgreSQL master-ID sequence. These are synthetic data,
        # not a simulated model, CAF authority or source historical record.
        record_id = -900001
        self.env.cr.execute('SELECT id FROM l10n_cl_dte_caf WHERE id=%s', [record_id])
        self.assertFalse(self.env.cr.fetchone(), 'Synthetic CAF identity already used')
        self.env.cr.execute('''INSERT INTO l10n_cl_dte_caf
            (id,filename,company_id,l10n_latam_document_type_id,start_nb,final_nb,issued_date,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
            [record_id, values['filename'], self.company.id, self.document.id, 50, 101,
             values['issued_date'], 'in_use'])
        record = self.manager_model().browse(record_id)
        self.assertEqual(record.exists().ids, [record_id], 'Negative fixture must be a persisted ORM record')
        self.env['ir.attachment'].with_context(allowed_company_ids=[self.company.id]).create({
            'name': values['filename'], 'type': 'binary', 'res_model': record._name,
            'res_id': record_id, 'res_field': 'caf_file', 'company_id': self.company.id,
            'datas': base64.b64encode(self.original), 'mimetype': 'application/xml'})
        record.invalidate_recordset(['caf_file'])
        return record

    def attachment(self, record):
        return self.env['ir.attachment'].search([
            ('res_model', '=', record._name), ('res_id', '=', record.id), ('res_field', '=', 'caf_file')])

    def assert_private_roundtrip(self):
        record = self.custody_record()
        original_fields = ['filename', 'company_id', 'l10n_latam_document_type_id',
                           'start_nb', 'final_nb', 'issued_date', 'status', 'write_date']
        before = record.read(original_fields)
        attachment = self.attachment(record)
        self.assertEqual(len(attachment), 1)
        before_attachment = attachment.read(['checksum', 'file_size', 'public', 'write_date'])
        for _ in range(2):
            self.assertEqual(hashlib.sha256(record._step_custody_original_bytes()).hexdigest(),
                             hashlib.sha256(self.original).hexdigest())
            metadata = record.step_custody_metadata()
            self.assertFalse(metadata['authority_verified'])
            self.assertFalse(metadata['folio_operations_enabled'])
            self.assertNotIn('PRIVATE KEY', json.dumps(metadata))
        self.assertEqual(record.read(original_fields), before)
        self.assertEqual(attachment.read(['checksum', 'file_size', 'public', 'write_date']), before_attachment)
        self.assertFalse(attachment.public)
        self.assertFalse(attachment.access_token)
        self.assertIn('/steps/caf/custody/', record.step_custody_download()['url'])

    def assert_original_roles(self):
        record = self.custody_record()
        employee = record.with_user(self.employee).with_context(allowed_company_ids=[self.company.id])
        with self.assertRaises(AccessError):
            employee._step_custody_original_bytes()
        stock = record.with_user(self.stock_manager).with_context(allowed_company_ids=[self.company.id])
        self.assertFalse(self.stock_manager.has_group('account.group_account_manager'))
        self.assertEqual(hashlib.sha256(stock._step_custody_original_bytes()).hexdigest(),
                         hashlib.sha256(self.original).hexdigest())

    def assert_company_scope(self):
        record = self.custody_record()
        with self.assertRaises(AccessError):
            record.with_context(allowed_company_ids=[self.other_company.id])._step_custody_original_bytes()
        self.env.cr.execute('UPDATE l10n_cl_dte_caf SET company_id=NULL WHERE id=%s', [record.id])
        record.invalidate_recordset(['company_id'])
        with self.assertRaises(AccessError):
            record._step_custody_original_bytes()
        self.assertFalse(record.company_id)

    def assert_no_public_or_token(self):
        record = self.custody_record()
        attachment = self.attachment(record)
        for values in ({'public': True}, {'access_token': 'SYNTHETIC_FORBIDDEN_TOKEN'}):
            with self.assertRaises(AccessError):
                attachment.write(values)
        attachment.invalidate_recordset(['public', 'access_token'])
        self.assertFalse(attachment.public)
        self.assertFalse(attachment.access_token)
        # _search intentionally hides Binary-field attachments unless the
        # domain names res_field. Count the real stored CAF files explicitly.
        domain = [('res_model', '=', record._name), ('res_field', '=', 'caf_file')]
        count = self.env['ir.attachment'].search_count(domain)
        self.assertIn(attachment.id, self.env['ir.attachment'].search(domain).ids)
        with self.assertRaises(AccessError):
            self.env['ir.attachment'].with_context(default_public=True).create({
                'name': 'SYNTHETIC must rollback.xml', 'res_model': record._name, 'res_id': record.id,
                'res_field': 'caf_file', 'datas': base64.b64encode(self.original)})
        self.assertEqual(self.env['ir.attachment'].search_count(domain), count)

    def assert_attachment_immutable(self):
        record = self.custody_record()
        attachment = self.attachment(record)
        for values in ({'datas': base64.b64encode(b'changed')}, {'res_id': 999999}, {'res_model': 'res.partner'}):
            with self.assertRaises(AccessError):
                attachment.write(values)
        with self.assertRaises(AccessError):
            attachment.unlink()
        unrelated = self.env['ir.attachment'].create({
            'name': 'SYNTHETIC_UNRELATED.xml', 'res_model': 'res.company', 'res_id': self.company.id,
            'datas': base64.b64encode(self.original)})
        with self.assertRaises(AccessError):
            unrelated.write({'res_model': record._name, 'res_id': record.id, 'res_field': 'caf_file'})
        self.assertEqual(hashlib.sha256(record._step_custody_original_bytes()).hexdigest(),
                         hashlib.sha256(self.original).hexdigest())
        # Only this synthetic fixture becomes a previously empty CAF. Keep its
        # original metadata unchanged, then exercise direct attachment creation
        # (which cannot rely on the CE model's upload preparation).
        self.env.cr.execute('DELETE FROM ir_attachment WHERE id=ANY(%s)', [attachment.ids])
        attachment.invalidate_recordset()
        record.invalidate_recordset(['caf_file'])
        attachments = self.env['ir.attachment'].with_user(self.manager).with_context(
            allowed_company_ids=[self.company.id])
        values = {'name': 'SYNTHETIC_MISMATCH.xml', 'res_model': record._name,
                  'res_id': record.id, 'res_field': 'caf_file'}
        for original, changed in ((b'<TD>33</TD>', b'<TD>34</TD>'),
                                  (b'<D>50</D>', b'<D>51</D>'),
                                  (b'<H>101</H>', b'<H>102</H>'),
                                  (b'<FA>2026-10-01</FA>', b'<FA>2026-10-02</FA>')):
            raw = self.original.replace(original, changed)
            with self.assertRaises(AccessError):
                attachments.create(dict(values, datas=base64.b64encode(raw)))
            self.assertFalse(self.attachment(record))
        with self.assertRaises(AccessError):
            attachments.with_context(default_public=True).create(
                dict(values, datas=base64.b64encode(self.original)))
        self.assertFalse(self.attachment(record))

    def assert_cached_download_revoked(self):
        record = self.custody_record()
        binary = self.env['ir.binary'].with_user(self.manager).with_context(allowed_company_ids=[self.company.id])
        with real_request_context(binary.env):
            cached = binary._find_record(res_model=record._name, res_id=record.id, field='caf_file')
            stream = binary._record_to_stream(cached, 'caf_file')
            self.assertEqual(hashlib.sha256(stream.read()).hexdigest(), hashlib.sha256(self.original).hexdigest())
            self.manager.write({'groups_id': [Command.unlink(self.env.ref('account.group_account_manager').id)]})
            for stale in (cached, self.attachment(record).sudo()):
                with self.assertRaises(AccessError):
                    binary._record_to_stream(stale, 'caf_file' if stale._name == record._name else 'raw')
            with self.assertRaises(AccessError):
                binary._find_record(res_model=record._name, res_id=record.id, field='caf_file')

    def assert_no_fiscal_operation(self):
        record = self.custody_record()
        before = record.read(['status', 'start_nb', 'final_nb', 'write_date'])
        with self.assertRaises(UserError):
            record.step_custody_reserve_folio()
        self.assertEqual(record.read(['status', 'start_nb', 'final_nb', 'write_date']), before)
