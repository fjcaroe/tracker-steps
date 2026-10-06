from lxml import etree

from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFreightMasters(TransactionCase):
    def test_quick_create_cold_mode_uses_name_not_technical_identifier(self):
        model = self.env['step.freight.cold.mode'].with_user(self.operator)
        record_id, label = model.name_create('QA Modalidad nueva desde selector')
        self.assertEqual(label, 'QA Modalidad nueva desde selector')
        self.assertEqual(model.browse(record_id).name, label)
        self.assertIn((record_id, label), model.name_search('QA Modalidad nueva desde selector'))

    def test_tariff_selectors_resolve_correct_masters_and_complete_route_form(self):
        arch = etree.fromstring(self.env['step.freight.tariff'].with_user(self.operator).get_view(
            view_id=self.env.ref('step_operations_ui.view_freight_tariff_code_form').id, view_type='form')['arch'])
        route = arch.xpath('//field[@name="route_id"]')[0]
        self.assertIn("'no_quick_create': True", route.get('options'))
        self.assertIn('view_freight_route_form', route.get('context'))
        self.assertEqual(self.env['step.freight.tariff.line']._fields['route_id'].comodel_name, 'step.freight.route')
        self.assertEqual(self.env['step.freight.tariff.line']._fields['cold_mode_id'].comodel_name, 'step.freight.cold.mode')

    def test_all_freight_models_and_fields_have_native_names(self):
        from ..native_schema import MODELS
        for old, model in MODELS.items():
            self.assertNotIn(old, self.env.registry.models)
            self.assertFalse([name for name in self.env[model]._fields if name.startswith('x_')], model)
            self.assertFalse(self.env['ir.model.fields'].search([('model', '=', model), ('state', '=', 'manual')]), model)
        for action in self.env['ir.actions.server'].search([('model_id.model', 'in', list(MODELS.values()))]):
            self.assertEqual(action.model_name, action.model_id.model, 'Automation still points to an old model')
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = cls.env['res.users'].create({
            'name': 'QA Fletes operador', 'login': 'qa_freight_master_operator',
            'email': 'qa-freight@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
            'company_id': cls.env.company.id,
            'company_ids': [(6, 0, [cls.env.company.id])],
        })

    def _form(self, model, prefix, action_xmlid):
        action = self.env.ref('step_operations_ui.' + action_xmlid)
        form_id = dict((kind, view) for view, kind in action.views)['form']
        expected = self.env.ref('step_operations_ui.view_freight_' + prefix + '_form')
        self.assertEqual(form_id, expected.id)
        user_model = self.env[model].with_user(self.operator)
        arch = etree.fromstring(user_model.get_view(view_id=form_id, view_type='form')['arch'])
        self.assertTrue(arch.xpath('//chatter'))
        return Form(user_model, view=expected)

    def test_operator_create_edit_route_and_open_chatter(self):
        form = self._form('step.freight.route', 'route',
                          'tramo_de_flete_0d34e499-bb52-47a3-a65e-9ac00a4c336e')
        form.name = 'QA Tramo prueba'
        form.origin = 'Fundo QA'
        form.destination = 'Planta QA'
        form.km_from = 19
        form.km_to = 29
        route = form.save()
        self.assertEqual(route.display_name, 'QA Tramo prueba')
        self.assertEqual(route.legacy_origin, 'Fundo QA')
        self.assertEqual(route.legacy_company_id, route.company_id)
        self.assertEqual(route._get_thread_with_access(route.id), route)
        message = route.message_post(body='Revisión del tramo', message_type='comment')
        self.assertIn(message, route.message_ids)
        with Form(route, view=self.env.ref('step_operations_ui.view_freight_route_form')) as edit:
            edit.destination = 'Puerto QA'
        self.assertEqual(route.legacy_destination, 'Puerto QA')
        route.write({'legacy_origin': 'Origen importado QA'})
        self.assertEqual(route.origin, 'Origen importado QA')

    def test_operator_create_edit_cold_mode_and_use_in_tariff(self):
        form = self._form('step.freight.cold.mode', 'cold_mode', 'action_freight_cold_mode')
        form.name = 'Mixto QA'
        form.code = '05'
        form.min_temperature = 1
        form.max_temperature = 8
        cold = form.save()
        self.assertEqual(cold.display_name, 'Mixto QA')
        self.assertEqual(cold._get_thread_with_access(cold.id), cold)
        self.assertIn(cold.message_post(body='Revisión de modalidad', message_type='comment'), cold.message_ids)
        with Form(cold, view=self.env.ref('step_operations_ui.view_freight_cold_mode_form')) as edit:
            edit.code = '06'
        line = self.env['step.freight.tariff.line'].with_user(self.operator).create({
            'tariff_id': self.env['step.freight.tariff'].with_user(self.operator).create({
                'name': 'Tarifa con modalidad QA'}).id,
            'cold_mode_id': cold.id,
        })
        self.assertEqual(line.cold_mode_id.code, '06')
        self.assertEqual(line.cold_mode_id.display_name, 'Mixto QA')

    def test_masters_have_no_active_studio_views_or_manual_fields(self):
        models = ['step.freight.route', 'step.freight.cold.mode']
        self.assertFalse(self.env['ir.model.fields'].search([
            ('model', 'in', models), ('state', '=', 'manual')]))
        data = self.env['ir.model.data'].search([
            ('module', '=', 'studio_customization'), ('model', '=', 'ir.ui.view')])
        self.assertFalse(self.env['ir.ui.view'].browse(data.mapped('res_id')).exists().filtered(
            lambda view: view.active and view.model in models))
        for prefix, model in [('route', models[0]), ('cold_mode', models[1])]:
            menu = self.env.ref('step_operations_ui.menu_freight_' + ('routes' if prefix == 'route' else 'cold_modes'))
            self.assertTrue(menu.active)
            self.assertEqual(menu.action.res_model, model)
            default = self.env[model].with_user(self.operator).get_view(view_type='form')
            self.assertEqual(default['id'], self.env.ref('step_operations_ui.view_freight_' + prefix + '_form').id)
