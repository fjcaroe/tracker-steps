from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProducerAnalyticCenter(TransactionCase):
    def test_estimate_uses_native_account_and_form_compiles(self):
        model = self.env['step.export.estimate']
        self.assertEqual(model._fields['cost_center_id'].comodel_name, 'account.analytic.account')
        # T35 deliberately omits this legacy header field from the form, while
        # existing integrations and history must still use the native account.
        plan = self.env['account.analytic.plan'].create({'name': 'Producer native plan QA'})
        center = self.env['account.analytic.account'].create({
            'name': 'Producer native center QA', 'code': 'PROD-QA', 'plan_id': plan.id,
            'company_id': self.env.company.id,
        })
        estimate = model.create({'name': 'Producer analytic FK QA', 'cost_center_id': center.id})
        self.assertEqual(estimate.cost_center_id, center)
        self.assertIn('season_id', model.get_view(view_type='form')['arch'])
