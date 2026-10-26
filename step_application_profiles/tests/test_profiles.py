from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.exceptions import AccessError
from ..hooks import post_init_hook


@tagged('post_install','-at_install')
class ApplicationProfilesCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.users={}
        for app in ('packing','export','producers'):
            for level in ('read','operation','manager'):
                cls.users[app,level]=new_test_user(cls.env,login='qa114-%s-%s'%(app,level),
                    groups='base.group_user,step_application_profiles.%s_%s'%(app,level))

    def acl(self,app,level,model,mode):
        return self.env['ir.model.access'].with_user(self.users[app,level]).check(model,mode,raise_exception=False)

    def test_consultation_is_server_readonly_in_each_application(self):
        for app,model in [('packing','step.packing.production'),('export','step.export.forecast'),('producers','step.producer.purchase.contract')]:
            self.assertTrue(self.acl(app,'read',model,'read'))
            for mode in ('create','write','unlink'):self.assertFalse(self.acl(app,'read',model,mode))

    def test_operations_can_work_but_cannot_delete_documents(self):
        for app,model in [('packing','step.packing.production'),('export','step.export.forecast'),('producers','step.producer.purchase.contract')]:
            for mode in ('read','create','write'):self.assertTrue(self.acl(app,'operation',model,mode))
            self.assertFalse(self.acl(app,'operation',model,'unlink'))

    def test_application_administration_is_not_system_or_finance_administration(self):
        for app,model in [('packing','step.packing.production'),('export','step.export.forecast'),('producers','step.producer.purchase.contract')]:
            user=self.users[app,'manager']
            self.assertTrue(self.acl(app,'manager',model,'unlink'))
            self.assertFalse(user.has_group('base.group_system'))
            self.assertFalse(user.has_group('account.group_account_manager'))
        with self.assertRaises(AccessError):
            self.env['step.packing.analytic.rule'].with_user(self.users['packing','manager']).create({})

    def test_unselected_applications_are_denied_beyond_menu_visibility(self):
        self.assertFalse(self.acl('packing','operation','step.producer.preliq.price','write'))
        self.assertFalse(self.acl('export','operation','step.packing.production','read'))
        self.assertFalse(self.acl('producers','operation','step.export.forecast','read'))

    def test_readonly_profiles_cannot_write_shared_inventory_or_products(self):
        for model in ('stock.picking','stock.move','stock.quant.package','product.product'):
            self.assertTrue(self.acl('packing','read',model,'read'))
            self.assertFalse(self.acl('packing','read',model,'write'))
        self.assertTrue(self.acl('packing','operation','stock.picking','create'))
        self.assertFalse(self.acl('packing','operation','product.product','create'))
        self.assertTrue(self.acl('packing','manager','product.product','create'))

    def test_menu_visibility_matches_application_selection(self):
        refs={'packing':'step_packing_operations.menu_packing_operations_root','export':'step_export.menu_step_export_root',
              'producers':'step_producers.menu_step_producers_root'}
        for app in refs:
            ids=self.env['ir.ui.menu'].with_user(self.users[app,'operation'])._visible_menu_ids()
            self.assertIn(self.env.ref(refs[app]).id,ids)
            for other in refs:
                if other!=app:self.assertNotIn(self.env.ref(refs[other]).id,ids)

    def test_group_changes_take_effect_without_restart_and_lookup_dependencies_read(self):
        user=self.users['packing','read']
        self.assertFalse(self.acl('packing','read','step.packing.production','write'))
        user.groups_id=[(4,self.env.ref('step_application_profiles.packing_operation').id)]
        self.assertTrue(self.acl('packing','read','step.packing.production','write'))
        self.assertTrue(self.acl('packing','read','step.producer.purchase.contract','read'))
        self.assertFalse(self.acl('packing','read','step.producer.purchase.contract','write'))

    def test_profile_setup_is_idempotent_and_existing_user_memberships_are_unchanged(self):
        before={user.id:user.groups_id.ids for user in self.env['res.users'].with_context(active_test=False).search([])}
        count=self.env['ir.model.access'].search_count([])
        post_init_hook(self.env)
        self.assertEqual(self.env['ir.model.access'].search_count([]),count)
        self.assertEqual({user.id:user.groups_id.ids for user in self.env['res.users'].with_context(active_test=False).search([])},before)

    def test_unprofiled_legacy_users_keep_their_native_permissions(self):
        user=new_test_user(self.env,login='qa114-legacy',groups='base.group_user,stock.group_stock_user')
        self.assertIsNone(user._step_application_levels())
        self.assertTrue(self.env['ir.model.access'].with_user(user).check('step.packing.production','write'))

    def test_application_manager_does_not_bypass_company_record_rules(self):
        other=self.env['res.company'].create({'name':'QA114 otra empresa'})
        ot=self.env['step.packing.production'].with_company(other).create({'company_id':other.id})
        with self.assertRaises(AccessError):
            ot.with_user(self.users['packing','manager']).with_context(allowed_company_ids=self.env.company.ids).read(['name'])
