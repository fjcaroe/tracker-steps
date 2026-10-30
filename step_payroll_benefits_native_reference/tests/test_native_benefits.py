"""Real native catalogue/value/form/ACL reference; no OCA aliases or paid runs."""
from unittest import TestCase

from lxml import etree
from psycopg2 import sql
from odoo import api, Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class NativeBenefitReferenceCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private native benefit reference',
            'country_id': cls.env.ref('base.cl').id})
        cls.actor = cls.env['res.users'].with_context(no_reset_password=True).create({'name': 'Private native benefit manager',
            'login': 'private-native-benefit-manager', 'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'groups_id': [Command.set([cls.env.ref(alias).id for alias in ('base.group_user',
                'hr_contract.group_hr_contract_manager', 'hr.group_hr_manager', 'hr_payroll.group_hr_payroll_manager')])]})
        cls.scope = api.Environment(cls.env.cr, cls.actor.id, dict(cls.env.context,
            allowed_company_ids=cls.company.ids, lang='en_US', tracking_disable=True), su=False)
        configurator = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private native benefit configurator', 'login': 'private-native-benefit-configurator',
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'groups_id': [Command.set([cls.env.ref('base.group_user').id, cls.env.ref('base.group_system').id])]})
        cls.configuration_scope = api.Environment(cls.env.cr, configurator.id,
            dict(cls.scope.context), su=False)
        cls.kind = cls.scope['hr.payroll.structure.type'].create({'name': 'Private native benefit type'})

    def _snapshot(self):
        self.env.flush_all()
        self.env.cr.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind IN ('r','p') AND c.relname LIKE 'hr_contract_salary_%' ORDER BY c.relname")
        result = {}
        for name, in self.env.cr.fetchall():
            self.env.cr.execute(sql.SQL('SELECT to_jsonb(t) FROM {} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(name)))
            result[name] = self.env.cr.fetchall()
        return result

    def _benefit(self):
        catalogue_type = self.scope['hr.contract.salary.benefit.type'].search([], limit=1)
        self.assertTrue(catalogue_type)
        # Provision the known technical field through the fixture author;
        # catalogue creation and all business operations use the normal actor.
        wage_field = self.env['ir.model.fields'].search([('model', '=', 'hr.contract'), ('name', '=', 'wage')])
        self.assertEqual(len(wage_field), 1)
        return self.scope['hr.contract.salary.benefit'].create({'name': 'Private native benefit reference',
            'benefit_type_id': catalogue_type.id, 'structure_type_id': self.kind.id,
            'res_field_id': wage_field.id, 'field': 'wage'})

    def test_original_model_inverse_real_catalogue_and_value_preserve_all_existing_rows(self):
        self.assertNotIn('hr.contract.advantage', self.scope.registry)
        self.assertFalse(self.scope.su)
        model = self.scope['hr.contract.salary.benefit']
        field = self.scope['hr.payroll.structure.type']._fields['salary_benefits_ids']
        self.assertEqual((field.type, field.comodel_name, field.inverse_name),
            ('one2many', 'hr.contract.salary.benefit', 'structure_type_id'))
        self.assertEqual(model._fields['structure_type_id'].ondelete, 'restrict')
        before = self._snapshot()
        self.assertEqual(len(before), 14)
        # Standard ORM savepoint rollback is deliberate test cleanup; no
        # original catalogue row, XML ID or production sequence is rewritten.
        with self.env.cr.savepoint() as point:
            benefit = self._benefit()
            values = {'name': 'Private native selectable value', 'benefit_id': benefit.id, 'value': 25.5}
            self.assertFalse(self.scope.user.has_group('base.group_system'))
            self.assertFalse(self.configuration_scope.su)
            # Native policy reserves value configuration to Settings. A
            # separate normal configurator provisions the real catalogue;
            # the HR manager retains only its existing selection/read access.
            with TestCase.assertRaises(self, AccessError):
                self.scope['hr.contract.salary.benefit.value'].create(values)
            value = self.configuration_scope['hr.contract.salary.benefit.value'].create(values).with_env(self.scope)
            self.assertIn(benefit, self.kind.salary_benefits_ids)
            self.assertIn(value, benefit.value_ids)
            self.assertEqual(value.read(['value'])[0]['value'], 25.5)
            benefit.description = '<p>Private catalogue edit</p>'
            self.assertIn('Private catalogue edit', benefit.description)
            point.rollback()
        self.assertEqual(self._snapshot(), before)

    def test_real_native_form_and_existing_role_policy_without_contract_salary_exposure(self):
        benefit = self._benefit()
        view = self.scope['hr.contract.salary.benefit'].get_view(view_type='form')
        self.assertEqual(etree.fromstring(view['arch'].encode()).tag, 'form')
        self.assertIn('structure_type_id', view['arch'])
        self.assertIn('benefit_type_id', view['arch'])
        actor = self.env['res.users'].with_context(no_reset_password=True).create({'name': 'Private native benefit internal',
            'login': 'private-native-benefit-internal', 'company_id': self.company.id,
            'company_ids': [Command.set(self.company.ids)], 'groups_id': [Command.set(self.env.ref('base.group_user').ids)]})
        self.assertEqual(benefit.with_user(actor).read(['name'])[0]['name'], benefit.name)
        with TestCase.assertRaises(self, AccessError):
            benefit.with_user(actor).write({'name': 'Forbidden native edit'})
        with TestCase.assertRaises(self, AccessError):
            benefit.with_user(actor).unlink()

    def test_reference_does_not_install_oca_or_import_the_native_family(self):
        self.env.cr.execute("SELECT name,license FROM ir_module_module WHERE name IN "
            "('hr_contract_salary','hr_payroll','payroll','payroll_contract_advantages') AND state='installed' ORDER BY name")
        installed = dict(self.env.cr.fetchall())
        self.assertEqual(installed.get('hr_contract_salary'), 'OEEL-1')
        self.assertEqual(installed.get('hr_payroll'), 'OEEL-1')
        self.assertNotIn('payroll', installed)
        self.assertNotIn('payroll_contract_advantages', installed)
        before = self._snapshot()
        self.scope['hr.contract.salary.benefit'].search([]).read(['name', 'structure_type_id'])
        self.assertEqual(self._snapshot(), before)
