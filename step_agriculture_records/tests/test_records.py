from lxml import etree
from odoo.tests import TransactionCase, Form, tagged
from odoo.tests.common import new_test_user
from odoo.exceptions import AccessError
from odoo.addons.step_management_costs.tests.test_management_costs import make_center
from odoo.addons.step_agriculture_records.schema import MODELS
from odoo.addons.step_agriculture_records.models.cost_center import ACTIVITIES


def assert_fields(case, model, node):
    for child in node:
        if child.tag == 'field':
            field = case.env[model]._fields.get(child.get('name'))
            case.assertTrue(field, (model, child.get('name')))
            if field.relational:
                for view in child:
                    if view.tag in ('form', 'list', 'kanban'):
                        assert_fields(case, field.comodel_name, view)
        else:
            assert_fields(case, model, child)


@tagged('post_install', '-at_install')
class AgricultureRecordsCase(TransactionCase):
    def test_native_models_views_and_document_roundtrip(self):
        for model in MODELS.values():
            with self.subTest(model=model):
                records = self.env[model]
                meta = self.env['ir.model'].search([('model', '=', model)])
                self.assertEqual(meta.state, 'base')
                self.assertFalse(any(name.startswith('x_') for name in records._fields))
                suffix = model.removeprefix('step.agriculture.').replace('.', '_')
                for kind in ('form', 'list', 'search', 'graph', 'pivot'):
                    view = self.env.ref('step_agriculture_records.view_' + suffix + '_' + kind)
                    arch = records.get_view(view_id=view.id, view_type=kind)['arch']
                    assert_fields(self, model, etree.fromstring(arch))
                if '.archive.' in model:
                    continue
                with Form(records, view='step_agriculture_records.view_' + suffix + '_form') as form:
                    if not records._fields['name'].readonly:
                        form.name = 'QA T103 documento'
                record = form.record
                self.assertTrue(record.name)
                with Form(record, view='step_agriculture_records.view_' + suffix + '_form'):
                    pass

    def test_cost_center_filters_counts_and_crew_relations(self):
        user = new_test_user(self.env, login='qa_t103_agriculture',
                            groups='base.group_user,step_management_costs.group_management_manager')
        plan = self.env['account.analytic.plan'].create({'name': 'QA T103 plan'})
        first = make_center(self.env, plan, 'QA103A', 'QA T103 cuartel A', self.env.company, plants=100, hectares=1)
        second = make_center(self.env, plan, 'QA103B', 'QA T103 cuartel B', self.env.company, plants=100, hectares=1)
        forecast = self.env['step.agriculture.harvest.forecast'].with_user(user)
        with Form(forecast.with_context(default_cost_center_id=first.id),
                  view='step_agriculture_records.view_harvest_forecast_form') as form:
            form.name = 'QA T103 pronóstico A'
        own = form.record
        other = forecast.create({'name': 'QA T103 pronóstico B', 'cost_center_id': second.id})
        center = first.with_user(user)
        action = center.with_context(agriculture_activity='forecast').action_agriculture_activity()
        selected = forecast.search(action['domain'])
        self.assertIn(own, selected)
        self.assertNotIn(other, selected)
        self.assertEqual(center.agriculture_forecast_count, len(selected))
        self.assertEqual(action['context']['default_cost_center_id'], first.id)
        from_directory = center.with_context(agriculture_activity='forecast', create=False,
                                              edit=False, delete=False,
                                              form_view_ref='step_hr.step_view_account_analytic_account_form')
        document_action = from_directory.action_agriculture_activity()
        self.assertFalse({'create', 'edit', 'delete', 'form_view_ref'} & set(document_action['context']))
        self.assertEqual(document_action['context']['default_cost_center_id'], first.id)
        for key, (_, model, relation) in ACTIVITIES.items():
            if not self.env[model].with_user(user).has_access('read'):
                self.assertFalse(center['agriculture_can_' + key])
                self.assertEqual(center['agriculture_' + key + '_count'], 0)
                with self.assertRaises(AccessError):
                    center.with_context(agriculture_activity=key).action_agriculture_activity()
                continue
            action = center.with_context(agriculture_activity=key).action_agriculture_activity()
            self.assertEqual(action['domain'], [(relation, '=', center.id)])
            count = self.env[model].with_user(user).search_count(action['domain'])
            self.assertEqual(center['agriculture_' + key + '_count'], count)

    def test_application_calculation_and_folio_are_native(self):
        app = self.env['step.agriculture.application'].create({
            'name': 'Nuevo', 'total_hectreas': 2, 'mojamiento_por_h': 100,
            'capacidad_lts_aplicadora': 50,
        })
        self.assertNotIn(app.name, ('Nuevo', '/'))
        self.assertEqual(app.total_lts_mezca, 200)
        self.assertEqual(app.maquinadas, 4)
        app.capacidad_lts_aplicadora = 0
        self.assertEqual(app.maquinadas, 0)
        actions = self.env['base.automation'].search([('model_id.model', 'in', list(MODELS.values())), ('active', '=', True)])
        self.assertFalse(actions)

    def test_original_tag_states_remain_the_same_master(self):
        states = self.env['step.agriculture.harvest.tag.state']
        state = states.create({'name': 'QA T103 estado original', 'code': 'QA103'})
        tag = self.env['step.agriculture.harvest.tag'].create({'name': 'QA T103 tarja', 'tag_state_id': state.id})
        self.assertEqual(tag.tag_state_id, state)
        self.assertEqual(tag.tag_state_id.code, 'QA103')
        self.assertEqual(tag._fields['tag_state_id'].comodel_name, 'step.agriculture.harvest.tag.state')

    def test_product_labor_group_is_required_only_for_labor(self):
        product = self.env['product.template'].create({'name': 'QA T103 insumo', 'is_labor': False})
        self.assertFalse(product.grupo_labor)
        form = Form(self.env['product.template'])
        form.name = 'QA T103 labor'
        form.is_labor = True
        with self.assertRaises(AssertionError):
            form.save()
        form.grupo_labor = 'manten'
        self.assertEqual(form.save().grupo_labor, 'manten')
