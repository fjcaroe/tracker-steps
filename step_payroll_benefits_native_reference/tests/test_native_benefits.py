"""Real native catalogue/value/form/ACL reference; no OCA aliases or paid runs."""
from unittest import TestCase
from unittest.mock import patch

from lxml import etree
from psycopg2 import sql
from odoo import api, Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.original_benefit_cohort import (
    BenefitCohortError, admit_source_benefit_cohort, _source_facts, _require_empty_membership,
)
from odoo.addons.step_payroll_contracts.original_payroll_roles import (
    plan_original_payroll_role_bindings, verify_original_payroll_role_bindings,
)


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

    def test_actual_readonly_source_admits_empty_inverse_without_discarding_58_catalogue_rows(self):
        before = self._snapshot()
        # A separate real read-only Odoo cursor sees the committed original
        # cohort, never this class's uncommitted private fixture identities.
        with self.registry.cursor(readonly=True) as cr:
            cr.execute('SELECT id FROM hr_payroll_structure_type ORDER BY id')
            original_ids = [row[0] for row in cr.fetchall()]
            self.assertEqual(len(original_ids), 5)
            plan = admit_source_benefit_cohort(cr, original_ids, expected_database=self.env.cr.dbname)
            report = plan.metadata()
            self.assertTrue(report['transaction_read_only'])
            self.assertEqual(report['source_rows'], 58)
            self.assertEqual(len(report['family_rows']), 14)
            self.assertEqual(report['cohort_benefit_memberships'], 0)
            resume = next(row for row in plan.inbound_rows if row[0] == 'hr_contract_salary_resume')
            self.assertEqual(sum(row[1] for row in resume[2]), 5)
            self.assertEqual([row[1] for row in resume[2]], [3, 2])
            self.assertFalse(report['salary_benefits_ids_implemented'])
            self.assertFalse(report['native_benefit_engine_implemented'])
            self.assertFalse(report['integral_conversion'])
            self.assertEqual(admit_source_benefit_cohort(cr, original_ids,
                expected_database=self.env.cr.dbname), plan)
        self.assertEqual(self._snapshot(), before)

    def test_real_attached_benefit_blocks_cohort_without_altering_the_original_catalogue(self):
        self._benefit()
        before = self._snapshot()
        facts = _source_facts(self.env.cr, self.kind.ids, expected_database=self.env.cr.dbname)
        self.assertEqual(facts.metadata()['cohort_benefit_memberships'], 1)
        with TestCase.assertRaisesRegex(self, BenefitCohortError, 'nonempty-original-benefit-membership'):
            _require_empty_membership(facts)
        with TestCase.assertRaisesRegex(self, BenefitCohortError, 'source-transaction-must-be-readonly'):
            admit_source_benefit_cohort(self.env.cr, self.kind.ids, expected_database=self.env.cr.dbname)
        self.assertEqual(self._snapshot(), before)

    def test_unrelated_real_benefit_is_preserved_and_never_mistaken_for_empty_family(self):
        self._benefit()
        other = self.scope['hr.payroll.structure.type'].create({'name': 'Private separate benefit cohort'})
        before = self._snapshot()
        facts = _source_facts(self.env.cr, other.ids, expected_database=self.env.cr.dbname)
        self.assertEqual(facts.metadata()['cohort_benefit_memberships'], 0)
        self.assertEqual(facts.metadata()['source_rows'], 59)
        self.assertEqual(_require_empty_membership(facts), facts)
        self.assertFalse(facts.transaction_read_only)
        self.assertFalse(facts.metadata()['integral_conversion'])
        self.assertEqual(self._snapshot(), before)

    def _ensure_matching_oca_role_aliases(self, plan):
        """Keep aliases already supplied by the real native security provider."""
        data = self.env['ir.model.data']
        keys = ('module', 'name', 'model', 'res_id', 'noupdate')
        for binding in plan.bindings:
            existing = data.search([('module', '=', binding[0]), ('name', '=', binding[1])])
            self.assertLessEqual(len(existing), 1)
            if existing:
                self.assertEqual(tuple(existing[key] for key in keys), binding)
            else:
                data.create(dict(zip(keys, binding)))
        data.flush_model(list(keys))

    def test_two_new_role_aliases_preserve_actual_groups_memberships_and_common_policy(self):
        internal = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private plain payroll alias reader', 'login': 'private-plain-payroll-alias-reader',
            'company_id': self.company.id, 'company_ids': [Command.set(self.company.ids)],
            'groups_id': [Command.set(self.env.ref('base.group_user').ids)]})
        internal_scope = api.Environment(self.env.cr, internal.id, dict(self.scope.context), su=False)
        self.assertFalse(internal_scope.su)
        # Settings can imply native payroll manager in the original policy.
        # Establish the real bare actor's original rights before checking aliases.
        self.assertFalse(internal_scope.user.has_group('hr_payroll.group_hr_payroll_manager'))
        plan = plan_original_payroll_role_bindings(self.env.cr, expected_database=self.env.cr.dbname)
        before = self._snapshot()
        self._ensure_matching_oca_role_aliases(plan)
        result = verify_original_payroll_role_bindings(self.env.cr, plan, expected_database=self.env.cr.dbname)
        self.assertTrue(result['original_common_policy_exact'])
        self.assertFalse(result['common_model_grants_added'])
        self.assertFalse(result['functional_role_parity_certified'])
        self.assertEqual(self.scope.ref('payroll.group_payroll_user'), self.scope.ref('hr_payroll.group_hr_payroll_user'))
        self.assertEqual(self.scope.ref('payroll.group_payroll_manager'), self.scope.ref('hr_payroll.group_hr_payroll_manager'))
        self.assertTrue(self.scope.user.has_group('payroll.group_payroll_manager'))
        self.assertTrue(self.scope.user.has_group('hr_payroll.group_hr_payroll_manager'))
        definitions = self.scope['res.groups']._get_group_definitions()
        for suffix in ('user', 'manager'):
            original = 'hr_payroll.group_hr_payroll_' + suffix
            alias = 'payroll.group_payroll_' + suffix
            self.assertEqual(definitions.get_id(original), self.scope.ref(original).id)
            self.assertEqual(definitions.get_id(alias), self.scope.ref(alias).id)
            self.assertEqual(definitions.parse(alias).key, definitions.parse(original).key)
            self.assertTrue(self.scope.user.has_group(original))
            self.assertTrue(self.scope.user.has_group(alias))
        self.assertTrue(self.scope.user.has_groups('payroll.group_payroll_manager,!base.group_system'))
        self.assertTrue(self.scope.user.has_groups('hr_payroll.group_hr_payroll_manager,!base.group_system'))
        self.assertFalse(internal_scope.user.has_group('payroll.group_payroll_manager'))
        self.assertFalse(internal_scope.user.has_groups('payroll.group_payroll_manager,!base.group_system'))
        partner = self.env['res.partner'].create({'name': 'Private real alias permission record'})
        view = self.env['ir.ui.view'].create({'name': 'Private real alias permission form', 'model': 'res.partner',
            'arch': '<form><sheet><group><field name="name" groups="payroll.group_payroll_manager"/></group></sheet></form>'})
        manager_arch = self.scope['res.partner'].get_view(view_id=view.id, view_type='form')['arch']
        other_arch = internal_scope['res.partner'].get_view(view_id=view.id, view_type='form')['arch']
        self.assertTrue(etree.fromstring(manager_arch.encode()).xpath(".//field[@name='name']"))
        self.assertFalse(etree.fromstring(other_arch.encode()).xpath(".//field[@name='name']"))
        action = self.env['ir.actions.act_window'].create({'name': 'Private real alias permission action',
            'res_model': 'res.partner', 'view_mode': 'list,form'})
        menu = self.env['ir.ui.menu'].create({'name': 'Private real alias permission menu',
            'action': 'ir.actions.act_window,%s' % action.id,
            'groups_id': [Command.set(self.scope.ref('payroll.group_payroll_manager').ids)]})
        self.assertIn(menu.id, self.scope['ir.ui.menu']._visible_menu_ids())
        self.assertNotIn(menu.id, internal_scope['ir.ui.menu']._visible_menu_ids())
        with patch.object(self.scope['res.partner']._fields['name'], 'groups', 'payroll.group_payroll_manager'):
            self.env.registry.clear_cache()
            try:
                self.assertEqual(partner.with_env(self.scope).read(['name'])[0]['name'], partner.name)
                with TestCase.assertRaises(self, AccessError):
                    partner.with_env(internal_scope).read(['name'])
            finally:
                self.env.registry.clear_cache()
        self.assertEqual(verify_original_payroll_role_bindings(self.env.cr, plan,
            expected_database=self.env.cr.dbname), result)
        self.assertEqual(self._snapshot(), before)

    def test_role_alias_collision_and_real_added_common_acl_fail_without_repair_or_grants(self):
        plan = plan_original_payroll_role_bindings(self.env.cr, expected_database=self.env.cr.dbname)
        self._ensure_matching_oca_role_aliases(plan)
        self.assertTrue(self.scope.user.has_group('payroll.group_payroll_user'))  # Warm the actual core definitions.
        binding = plan.bindings[0]
        data = self.env['ir.model.data']
        alias = data.search([('module', '=', binding[0]), ('name', '=', binding[1])])
        original_alias_id = alias.id
        wrong_group = self.env.ref('base.group_user')
        self.assertNotEqual(binding[3], wrong_group.id)

        class PrivateAliasRollback(Exception):
            pass

        # Deliberately collide the actual technical alias only inside this
        # rollback savepoint. Never delete/recreate an existing provider alias.
        with TestCase.assertRaises(self, PrivateAliasRollback):
            with self.env.cr.savepoint():
                alias.write({'res_id': wrong_group.id})
                alias.flush_recordset(['res_id'])
                with TestCase.assertRaisesRegex(self, BenefitCohortError, 'alias-collision-no-update'):
                    plan_original_payroll_role_bindings(self.env.cr, expected_database=self.env.cr.dbname)
                self.assertEqual(alias.res_id, wrong_group.id)
                # The original role remains valid; the retargeted alias cannot
                # grant any other role or bypass field/view checks via caches.
                self.assertTrue(self.scope.user.has_group('hr_payroll.group_hr_payroll_manager'))
                with TestCase.assertRaises(self, AccessError):
                    self.scope.user.has_group(binding[0] + '.' + binding[1])
                with TestCase.assertRaises(self, AccessError):
                    self.scope.user.has_groups('!' + binding[0] + '.' + binding[1])
                with TestCase.assertRaises(self, AccessError):
                    self.scope['res.groups']._get_group_definitions().parse(binding[0] + '.' + binding[1], False)
                raise PrivateAliasRollback()
        restored = data.search([('module', '=', binding[0]), ('name', '=', binding[1])])
        self.assertEqual(restored.id, original_alias_id)
        self.assertEqual(tuple(restored[key] for key in ('module', 'name', 'model', 'res_id', 'noupdate')), binding)
        self.assertTrue(verify_original_payroll_role_bindings(self.env.cr, plan,
            expected_database=self.env.cr.dbname)['original_common_policy_exact'])
        before = self._snapshot()
        self.env['ir.model.access'].create({'name': 'Private unexpected original common-model grant',
            'model_id': self.env['ir.model']._get_id('hr.salary.rule'),
            'group_id': wrong_group.id, 'perm_read': True, 'perm_write': False,
            'perm_create': False, 'perm_unlink': False})
        with TestCase.assertRaisesRegex(self, BenefitCohortError, 'original-group-or-common-model-policy-changed'):
            verify_original_payroll_role_bindings(self.env.cr, plan, expected_database=self.env.cr.dbname)
        self.assertEqual(self._snapshot(), before)
