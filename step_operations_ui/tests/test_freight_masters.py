from lxml import etree

from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFreightMasters(TransactionCase):
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
        form = self._form('x_tramo_de_flete', 'route',
                          'tramo_de_flete_0d34e499-bb52-47a3-a65e-9ac00a4c336e')
        form.x_name = 'QA Tramo prueba'
        form.origin = 'Fundo QA'
        form.destination = 'Planta QA'
        form.x_studio_km_desde = 19
        form.x_studio_km_hasta = 29
        route = form.save()
        self.assertEqual(route.display_name, 'QA Tramo prueba')
        self.assertEqual(route.x_studio_lugar_desde, 'Fundo QA')
        self.assertEqual(route.x_studio_empresa, route.company_id)
        self.assertEqual(route._get_thread_with_access(route.id), route)
        message = route.message_post(body='Revisión del tramo', message_type='comment')
        self.assertIn(message, route.message_ids)
        with Form(route, view=self.env.ref('step_operations_ui.view_freight_route_form')) as edit:
            edit.destination = 'Puerto QA'
        self.assertEqual(route.x_studio_lugar_hasta, 'Puerto QA')
        route.write({'x_studio_lugar_desde': 'Origen importado QA'})
        self.assertEqual(route.origin, 'Origen importado QA')

    def test_operator_create_edit_cold_mode_and_use_in_tariff(self):
        form = self._form('x_modalidad_de_frio', 'cold_mode', 'action_freight_cold_mode')
        form.x_name = 'Mixto QA'
        form.x_studio_cdigo = '05'
        form.min_temperature = 1
        form.max_temperature = 8
        cold = form.save()
        self.assertEqual(cold.display_name, 'Mixto QA')
        self.assertEqual(cold._get_thread_with_access(cold.id), cold)
        self.assertIn(cold.message_post(body='Revisión de modalidad', message_type='comment'), cold.message_ids)
        with Form(cold, view=self.env.ref('step_operations_ui.view_freight_cold_mode_form')) as edit:
            edit.x_studio_cdigo = '06'
        line = self.env['x_tarifa_de_fletes_line_57b07'].with_user(self.operator).create({
            'x_tarifa_de_fletes_id': self.env['x_tarifa_de_fletes'].with_user(self.operator).create({
                'x_name': 'Tarifa con modalidad QA'}).id,
            'x_studio_modalidad_de_fro': cold.id,
        })
        self.assertEqual(line.x_studio_modalidad_de_fro.x_studio_cdigo, '06')
        self.assertEqual(line.x_studio_modalidad_de_fro.display_name, 'Mixto QA')

    def test_masters_have_no_active_studio_views_or_manual_fields(self):
        models = ['x_tramo_de_flete', 'x_modalidad_de_frio']
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
