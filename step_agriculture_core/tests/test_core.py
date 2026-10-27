from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, tagged

from ..hooks import adopt_legacy_records, preserve_legacy_xmlids
from ..ownership import FIELDS, MODELS, RECORDS


@tagged('post_install', '-at_install')
class AgricultureCoreCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Community agriculture test', 'login': 'community_agriculture_core_test',
            'email': 'agriculture-test@example.invalid',
            'company_id': cls.env.company.id,
            'company_ids': [Command.set(cls.env.company.ids)],
            'groups_id': [Command.set([cls.env.ref('base.group_user').id,
                                      cls.env.ref('analytic.group_analytic_accounting').id])],
        })

    def test_original_xmlids_and_tables(self):
        legacy_menu = self.env.ref('step_hr.menu_step_hr_root', raise_if_not_found=False)
        root = self.env.ref('step_agriculture_core.menu_agriculture_core')
        self.assertEqual(root.active, not bool(legacy_menu))
        for name, model in RECORDS.items():
            with self.subTest(xmlid=name):
                original = self.env.ref('step_hr.' + name)
                core = self.env.ref('step_agriculture_core.' + name)
                self.assertEqual(original, core)
                self.assertEqual(core._name, model)
        for model in MODELS:
            self.assertEqual(self.env[model]._table, model.replace('.', '_'))
        for model, names in FIELDS.items():
            for name in names:
                field = self.env.ref('step_hr.field_' + model.replace('.', '_') + '__' + name)
                self.assertEqual((field.model, field.name), (model, name))

    def test_real_master_relations_and_chatter(self):
        env = self.env(user=self.user)
        season = env['step.temporada'].create({'name': 'Migration season', 'code': 'MIG'})
        fundo = env['step.fundo'].create({'name': 'Migration fundo', 'fundo_code': 'MIG'})
        species = env['step.especie'].create({'name': 'Migration species', 'type_especie': 'frutal',
                                             'group_especie': 'poma'})
        group = env['step.grupo.variedad'].create({'name': 'Migration group', 'especie_id': species.id})
        variety = env['step.variedad'].create({'name': 'Migration variety', 'cod_variedad': 'MIG',
                                              'especie_id': species.id, 'grupo_variedad_id': group.id})
        plan = self.env['account.analytic.plan'].create({'name': 'Migration plan'})
        cost = env['account.analytic.account'].create({
            'name': 'Migration cost', 'plan_id': plan.id, 'fundo_id': fundo.id,
            'type_costo': 'fruta', 'etapa_costo': 'ope', 'tipo_fruta': 'conven',
            'especie_id': species.id, 'grupo_variedad_id': group.id, 'variedad_id': variety.id,
        })
        cuartel = env['step.cuartel.line'].create({'name': 'Cuartel', 'centro_id': cost.id, 'has_cuartel': 2.75})
        hilera = env['step.hilera.line'].create({'name': 'Hilera', 'centro_id': cost.id, 'cuartel_id': cuartel.id})
        self.assertEqual(cost.fundo_id, fundo)
        self.assertEqual(cost.variedad_id.especie_id, species)
        self.assertEqual(cost.hilera_line.cuartel_id, cuartel)
        self.assertEqual(hilera.centro_id, cost)
        self.assertEqual(cuartel.has_cuartel, 2.75)
        message = season.message_post(body='Preserved model chatter')
        self.assertEqual((message.model, message.res_id), ('step.temporada', season.id))
        for model, view in [('step.temporada', 'view_temporada_form'),
                            ('step.fundo', 'view_step_fundo_form'),
                            ('step.especie', 'view_step_especie_form'),
                            ('step.variedad', 'view_step_variedad_form'),
                            ('account.analytic.account', 'step_view_account_analytic_account_form')]:
            native_view = self.env.ref('step_agriculture_core.' + view)
            self.assertIn('arch', env[model].get_view(native_view.id, 'form'))
        with Form(env['step.fundo'], view='step_agriculture_core.view_step_fundo_form') as form:
            form.name = 'Native Community form'
        self.assertTrue(form.record.id)

    def test_permissions_not_widened_to_portal(self):
        portal = self.env['res.users'].create({
            'name': 'Portal agriculture test', 'login': 'portal_agriculture_core_test',
            'groups_id': [Command.set([self.env.ref('base.group_portal').id])],
        })
        for model in MODELS:
            with self.subTest(model=model), self.assertRaises(AccessError):
                self.env[model].with_user(portal).check_access('read')

    def test_adoption_idempotent_and_conflicts_fail(self):
        before = {name: self.env.ref('step_hr.' + name).id for name in RECORDS}
        adopt_legacy_records(self.env)
        preserve_legacy_xmlids(self.env)
        adopt_legacy_records(self.env)
        self.assertEqual(before, {name: self.env.ref('step_hr.' + name).id for name in RECORDS})
        alias = self.env['ir.model.data'].search([
            ('module', '=', 'step_agriculture_core'), ('name', '=', 'action_step_fundo')])
        alias.res_id = self.env.ref('step_agriculture_core.action_step_temporada').id
        with self.assertRaises(UserError):
            adopt_legacy_records(self.env)
