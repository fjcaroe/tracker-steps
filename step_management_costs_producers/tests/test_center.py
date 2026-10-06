from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProducerAnalyticCenter(TransactionCase):
    def test_estimate_uses_native_account_and_form_compiles(self):
        model = self.env['step.export.estimate']
        self.assertEqual(model._fields['cost_center_id'].comodel_name, 'account.analytic.account')
        self.assertIn('cost_center_id', model.get_view(view_type='form')['arch'])
