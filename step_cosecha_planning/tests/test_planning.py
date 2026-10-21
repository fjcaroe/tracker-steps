from odoo.tests import TransactionCase, tagged, Form
from odoo.tests.common import new_test_user
from odoo.exceptions import UserError
from odoo.addons.step_management_costs.tests.test_management_costs import make_center


@tagged('post_install', '-at_install')
class HarvestPlanningCase(TransactionCase):
    def test_shared_plan_generate_confirm_and_permissions(self):
        self.env=self.env(context=dict(self.env.context,tracking_disable=True,mail_create_nosubscribe=True,no_reset_password=True))
        company=self.env.company
        analytic=self.env['account.analytic.plan'].create({'name':'QA T100 plan'})
        center=make_center(self.env,analytic,'QA100','QA T100 cuartel',company,plants=100,hectares=1)
        unit=self.env['step.management.estimation.unit'].create({'name':'QA T100 bin','code':'QA100','kg_factor':400,'company_id':company.id})
        version=self.env['step.management.estimation.version'].create({'name':'QA T100 version','code':'QA100','season':'2026/2027','company_id':company.id})
        category=self.env['step.management.fruit.category'].create({'name':'QA T100 categoria','code':'QA100','company_id':company.id})
        fruit_class=self.env['step.management.fruit.class'].create({'name':'QA T100 clase','code':'QA100','category_id':category.id,'company_id':company.id})
        caliber=self.env['step.management.caliber.group'].create({'name':'QA T100 calibre','code':'QA100','company_id':company.id})
        curves={}
        for kind,lines in [('week',[{'week_number':45,'percentage':40},{'week_number':46,'percentage':60}]),('caliber',[{'caliber_group_id':caliber.id,'percentage':100}]),('class',[{'fruit_class_id':fruit_class.id,'percentage':100}])]:
            curve=self.env['step.management.estimation.curve'].create({'name':'QA T100 '+kind,'code':'QA100'+kind,'curve_type':kind,'company_id':company.id,'line_ids':[(0,0,l) for l in lines]})
            curve.action_validate();curves[kind]=curve
        estimation=self.env['step.management.estimation'].create({'version_id':version.id,'season':'2026/2027','company_id':company.id,'unit_id':unit.id,'method':'plants','default_yield_ue':1,'week_curve_id':curves['week'].id,'caliber_curve_id':curves['caliber'].id,'class_curve_id':curves['class'].id,'center_ids':[(6,0,center.ids)]})
        estimation.action_compute_lines();estimation.action_validate()
        user=new_test_user(self.env,login='qa_t100_operator',groups='step_management_costs.group_management_user',company_id=company.id,company_ids=[(6,0,company.ids)])
        readonly=new_test_user(self.env,login='qa_t100_readonly',groups='step_management_costs.group_management_readonly',company_id=company.id,company_ids=[(6,0,company.ids)])
        harvest_menu=self.env.ref('step_cosecha_planning.menu_harvest_plan')
        management_menu=self.env.ref('step_management_costs.menu_harvest_plan')
        self.assertEqual(harvest_menu.action,management_menu.action)
        for menu in (harvest_menu,management_menu):
            self.assertIn(menu.id,self.env['ir.ui.menu'].with_user(user)._visible_menu_ids())
        model=self.env[harvest_menu.action.res_model].with_user(user)
        plan=model.create({'company_id':company.id,'estimation_id':estimation.id})
        plan.action_generate();plan.action_confirm()
        self.assertEqual(plan.state,'confirmed')
        self.assertEqual(plan.total_kg,40000)
        self.assertEqual(plan.total_containers,100)
        self.assertEqual(len(plan.line_ids),2)
        shared=self.env[management_menu.action.res_model].with_user(readonly).browse(plan.id)
        self.assertEqual(shared.read(['confirmation_hash'])[0]['confirmation_hash'],plan.confirmation_hash)
        self.assertFalse(shared.has_access('write'))
        with self.assertRaises(UserError):plan.write({'round_up_containers':False})
        for kind,ref in [('form','step_management_costs.view_harvest_plan_form'),('list','step_management_costs.view_harvest_plan_list')]:
            self.assertTrue(model.get_view(view_id=self.env.ref(ref).id,view_type=kind)['arch'])

    def test_packaging_groups_roundtrip_in_existing_master(self):
        product=self.env['product.product'].create({'name':'QA T100 fruta','grupo_labor':'pack'})
        package=self.env['product.packaging'].create({'name':'QA T100 embalaje','product_id':product.id,'qty':10})
        self.assertFalse(package.step_packaging_group)
        for group in ('export','national','harvest'):
            with Form(package,view='step_export.view_step_export_packaging_form') as form:
                form.step_packaging_group=group
            self.assertEqual(package.step_packaging_group,group)
            self.assertEqual(package.qty,10)
            self.assertEqual(package.product_id,product)
        for ref,kind in [('product.product_packaging_form_view','form'),('product.product_packaging_tree_view','list'),('step_export.view_step_export_packaging_form','form'),('step_export.view_step_export_packaging_list','list')]:
            self.assertIn('step_packaging_group',package.get_view(view_id=self.env.ref(ref).id,view_type=kind)['arch'])
        pallet=self.env['stock.package.type'].create({'name':'QA T100 pallet'})
        self.assertEqual(self.env.ref('step_cosecha_planning.menu_package_type').action.res_model,pallet._name)
        self.assertEqual(self.env.ref('step_cosecha_planning.menu_packaging').action.res_model,package._name)
