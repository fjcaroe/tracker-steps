from datetime import date
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install')
class RegistrationCase(TransactionCase):
    def test_registration_keeps_text_dates_and_master_relation(self):
        aptitude = self.env['step.agriculture.pesticide.aptitude'].create({'name': 'QA Aptitude', 'code': '0001/A'})
        product = self.env['product.template'].create({'name': 'QA BPA', 'registration_aptitude_id': aptitude.id,
            'registration_concentration': '48 %p/v (480 g/l)', 'registration_formulation_code': '(SL)',
            'registration_first_authorized_on': '1985-09-04', 'registration_authorization_expires_on': '2025-09-04'})
        self.assertEqual(product.registration_aptitude_id, aptitude)
        self.assertEqual(product.registration_concentration, '48 %p/v (480 g/l)')
        self.assertEqual(product.registration_authorization_expires_on, date(2025, 9, 4))
        aptitude.active = False
        self.assertEqual(product.registration_aptitude_id, aptitude)

    def test_internal_user_can_manage_but_not_delete_master(self):
        user = self.env['res.users'].create({'name': 'QA BPA User', 'login': 'qa-bpa-registration',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        aptitude = self.env['step.agriculture.pesticide.aptitude'].with_user(user).create({'name': 'QA Operator'})
        aptitude.write({'code': '001'})
        self.assertEqual(aptitude.code, '001')
        with self.assertRaises(AccessError):
            aptitude.unlink()

    def test_portal_has_no_catalog_access(self):
        with self.assertRaises(AccessError):
            self.env['step.agriculture.pesticide.aptitude'].with_user(self.env.ref('base.public_user')).search([])
