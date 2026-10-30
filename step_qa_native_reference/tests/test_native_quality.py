"""Real native controls and consumer identities; no Community model aliases."""
import json
from unittest import TestCase

from odoo import api, Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tools import json_default
from odoo.addons.step_qa.models.quality_check import QualityCheck as OriginalStepsCheck
from odoo.addons.step_quality_contracts.access import original_quality_provider


@tagged('post_install', '-at_install')
class NativeQualityConsumerCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private native QA reference'})
        actor = cls.env['res.users'].with_context(no_reset_password=True).create({'name': 'Private native QA manager',
            'login': 'private-native-qa-manager', 'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'groups_id': [Command.set([cls.env.ref(alias).id for alias in ('base.group_user',
                'quality.group_quality_manager', 'stock.group_stock_user')])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=cls.company.ids,
            mail_notrack=True, tracking_disable=True, mail_create_nosubscribe=True, lang='en_US'), su=False)
        for code in ('quality.check', 'quality.point', 'quality.alert'):
            cls.env['ir.sequence'].create({'name': 'Private native QA numbering', 'code': code,
                'company_id': cls.company.id, 'implementation': 'no_gap', 'prefix': 'PRIVATE/QA/'})
        cls.team = cls.scope['quality.alert.team'].create({'name': 'Private native QA team', 'company_id': cls.company.id})
        cls.product = cls.env['product.product'].create({'name': 'Private native QA product'})

    def _check(self):
        return self.scope['quality.check'].create({'company_id': self.company.id, 'team_id': self.team.id,
            'test_type_id': self.scope.ref('quality_control.test_type_passfail').id,
            'measure_on': 'product', 'product_id': self.product.id})

    def _identities(self):
        self.env.cr.execute("SELECT to_jsonb(d) FROM ir_model_data d WHERE module IN ('step_qa','step_export_traceability') ORDER BY id")
        aliases = self.env.cr.fetchall()
        self.env.cr.execute("SELECT to_jsonb(v) FROM ir_ui_view v WHERE id IN (SELECT res_id FROM ir_model_data "
            "WHERE module IN ('step_qa','step_export_traceability') AND model='ir.ui.view') ORDER BY id")
        return aliases, self.env.cr.fetchall()

    def test_actual_native_controls_and_dashboard_without_replacing_their_model(self):
        self.assertNotIn('qc.inspection', self.scope.registry)
        self.assertEqual(original_quality_provider(self.scope)._name, 'quality.check')
        checks = self._check() | self._check()
        checks[0].do_pass()
        checks[1].do_fail()
        self.assertEqual(checks.mapped('quality_state'), ['pass', 'fail'])
        before = checks.read(['name', 'quality_state', 'control_date', 'company_id', 'write_date'])
        data = self.scope['quality.check'].get_step_qa_dashboard()
        self.assertEqual((data['checks']['total'], data['checks']['passed'], data['checks']['failed']), (2, 1, 1))
        self.assertEqual(checks.read(['name', 'quality_state', 'control_date', 'company_id', 'write_date']), before)
        json.dumps(data, default=json_default)

    def test_neutral_agricultural_summary_preserves_existing_ids_and_payload(self):
        model = self.scope['step.agriculture.inspection']
        records = model.create([{'name': 'PRIVATE/QA/INTERNAL/1', 'state': 'status1'},
            {'name': 'PRIVATE/QA/INTERNAL/2', 'state': 'status3'}])
        before = records.read(['name', 'state', 'write_date'])
        native = self.scope['quality.check']
        original = OriginalStepsCheck._step_qa_inspection_summary(native, [])
        self.assertEqual(native._step_qa_inspection_summary([]), original)
        self.assertEqual(native._step_qa_advisor_summary([]), OriginalStepsCheck._step_qa_advisor_summary(native, []))
        self.assertTrue(original['available'])
        self.assertGreaterEqual(original['total'], 2)
        self.assertEqual(records.read(['name', 'state', 'write_date']), before)

    def test_original_forms_aliases_and_traceability_provider_are_unchanged(self):
        before = self._identities()
        view = self.scope['quality.check'].get_view(view_id=self.scope.ref('step_qa.view_quality_check_form_step_qa').id, view_type='form')
        self.assertIn('quality_state', view['arch'])
        self.assertIn('point_id', view['arch'])
        self.assertEqual(self.scope['stock.quant.package']._fields['trace_panel'].store, False)
        self.assertEqual(self.scope['step.export.export']._fields['arrival_quality_id'].comodel_name, 'step.management.fruit.quality')
        self.scope['quality.check'].get_step_qa_dashboard(days=30)
        self.assertEqual(self._identities(), before)

    def test_normal_actor_scope_is_retained_with_incoming_sudo_and_cached_controls(self):
        check = self._check()
        check.sudo().read(['quality_state'])
        actor = self.env['res.users'].with_context(no_reset_password=True).create({'name': 'Private QA internal',
            'login': 'private-qa-internal', 'company_id': self.company.id, 'company_ids': [Command.set(self.company.ids)],
            'groups_id': [Command.set(self.env.ref('base.group_user').ids)]})
        with TestCase.assertRaises(self, AccessError):
            self.scope['quality.check'].with_user(actor).sudo().get_step_qa_dashboard()
