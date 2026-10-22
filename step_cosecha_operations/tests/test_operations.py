from lxml import etree
from odoo.tests import TransactionCase, Form, tagged
from odoo.tests.common import new_test_user
from odoo.addons.step_cosecha_operations.hooks import migrate_contractor_form


@tagged('post_install', '-at_install')
class HarvestOperationsCase(TransactionCase):
    def test_native_master_navigation_and_edit(self):
        manager = new_test_user(self.env, login='qa_t101',
                                groups='base.group_user,step_management_costs.group_management_manager')
        visible = self.env['ir.ui.menu'].with_user(manager)._visible_menu_ids()
        for key in ('fruit_class', 'tag_state', 'tag_type'):
            menu = self.env.ref('step_cosecha_operations.menu_' + key)
            self.assertIn(menu.id, visible)
            model = self.env[menu.action.res_model].with_user(manager)
            with Form(model) as f:
                f.name = 'QA T101 master'
                f.code = 'QA101'
                if key == 'fruit_class':
                    f.category_id = self.env['step.management.fruit.category'].create({
                        'name': 'QA T101 category', 'code': 'QA101', 'company_id': manager.company_id.id})
            record = f.record
            with Form(record) as f:
                f.name = 'QA T101 edited'
            self.assertEqual(model.browse(record.id).name, 'QA T101 edited')

    def test_contractor_crew_and_harvest_roundtrip(self):
        user = new_test_user(self.env, login='qa_t102', groups='base.group_user,hr.group_hr_user')
        partner = self.env['res.partner'].create({'name': 'QA contractor', 'step_contra': True})
        employee = self.env['hr.employee'].create({
            'name': 'QA contractor worker', 'is_contratista': True,
            'contratista_id': partner.id, 'company_id': user.company_id.id,
        })
        crews = self.env['hr.salary.custom'].with_user(user).with_context(step_default_contratista=1)
        with Form(crews) as f:
            f.name = 'QA crew'
            f.partner_id = partner
            with f.contract_line.new() as line:
                line.employee_id = employee
                line.hours = 8
        crew = f.record
        self.assertEqual(crew.contract_line.partner_id, partner)
        crew.action_progress()
        registries = self.env['step.cosecha.registry'].with_user(user).with_context(step_default_contratista=1)
        with Form(registries) as f:
            f.name = 'QA harvest'
            f.product_uom_id = self.env.ref('uom.product_uom_kgm')
            f.partner_id = partner
            f.salary_id_contrac = crew
        record = f.record
        self.assertEqual(record.type_tarea, 'contratista')
        self.assertEqual(record.partner_id, partner)
        self.assertEqual(record.registry_tarja_line.employee_id, employee)
        with Form(record) as f:
            f.tarja_kg = 400
            f.tarja_cajas = 20
        self.assertEqual(record.tarja_kg, 400)
        record.action_apro()
        self.assertEqual(record.state, 'apro')
        record.action_in()
        self.assertEqual(record.state, 'in')

    def test_effective_views_menus_and_idempotent_migration(self):
        migrate_contractor_form(self.env)
        migrate_contractor_form(self.env)
        menu = self.env.ref('step_cosecha.menu_step_cosecha_proceso')
        self.assertEqual(menu.parent_id, self.env.ref('step_cosecha.menu_step_cosecha_recepcion'))
        for name, model in [('fruit_class', 'step.management.fruit.class'),
                            ('tag_state', 'step.packing.tag.state'),
                            ('tag_type', 'step.packing.tag.type')]:
            action = self.env.ref('step_cosecha_operations.menu_' + name).action
            self.assertEqual(action.res_model, model)
            self.assertTrue(self.env[model].get_view(view_type='list')['arch'])
        arch = self.env['step.cosecha.registry'].get_view(
            view_id=self.env.ref('step_cosecha.view_step_cosecha_registry_form').id,
            view_type='form')['arch']
        root = etree.fromstring(arch)
        self.assertFalse(root.xpath(".//field[@name='employee_id_domain']/form//field[@name='firstname']"))
