import secrets
from psycopg2 import IntegrityError
from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessDenied, ValidationError


@tagged('post_install', '-at_install')
class EmailCase(TransactionCase):
    def fixture(self, login='Mi.Correo@example.invalid'):
        self.password = secrets.token_urlsafe(24)
        self.user = self.env['res.users'].with_context(no_reset_password=True, tracking_disable=True,
            mail_create_nosubscribe=True).create({'name':'QA correo', 'login':login, 'password':self.password,
                'groups_id':[Command.set(self.env.ref('base.group_user').ids)]})
        return self.user

    def test_new_and_legacy_email_case_and_literal_lookup(self):
        self.fixture('Caja%_QA@example.invalid')
        self.assertEqual(self.user.login, 'caja%_qa@example.invalid')
        self.env.cr.execute('UPDATE res_users SET login=%s WHERE id=%s', ['Caja%_QA@example.invalid', self.user.id])
        self.user.invalidate_recordset()
        for value in ('caja%_qa@example.invalid', 'CAJA%_QA@EXAMPLE.INVALID'):
            self.assertEqual(self.env['res.users'].search(self.env['res.users']._get_login_domain(value)), self.user)
        self.assertFalse(self.env['res.users'].search(self.env['res.users']._get_login_domain('cajaZZqa@example.invalid')))

    def test_duplicate_create_rename_archive_and_database_guard(self):
        self.fixture()
        with self.assertRaises(ValidationError): self.fixture('MI.CORREO@EXAMPLE.INVALID')
        other=self.env['res.users'].with_context(no_reset_password=True).create({'name':'QA otro','login':'otro-qa-email'})
        with self.assertRaises(ValidationError): other.login='MI.CORREO@EXAMPLE.INVALID'
        self.user.active=False
        with self.assertRaises(ValidationError): other.login='MI.CORREO@EXAMPLE.INVALID'
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env.cr.execute('UPDATE res_users SET login=%s WHERE id=%s',['MI.CORREO@EXAMPLE.INVALID', other.id])

    def test_native_password_and_inactive_account_protection(self):
        self.fixture()
        credential={'login':self.user.login,'password':self.password,'type':'password'}
        result=self.user.with_user(self.user)._check_credentials(credential, {'interactive':True})
        self.assertEqual(result['uid'], self.user.id)
        with self.assertRaises(AccessDenied):
            self.user.with_user(self.user)._check_credentials(dict(credential,password=self.password+'x'), {'interactive':True})
        self.user.active=False
        self.assertFalse(self.env['res.users'].search(self.env['res.users']._get_login_domain(self.user.login.upper())))

    def test_normalization_keeps_non_email_usernames_and_password(self):
        self.fixture('OperadorQA')
        self.assertFalse(self.env['res.users'].search(self.env['res.users']._get_login_domain('operadorqa')))
        self.user.login='CAMBIO@EXAMPLE.INVALID'
        self.assertEqual(self.user.login,'cambio@example.invalid')
        self.assertEqual(self.user.with_user(self.user)._check_credentials(
            {'login':self.user.login,'password':self.password,'type':'password'}, {'interactive':True})['uid'], self.user.id)
