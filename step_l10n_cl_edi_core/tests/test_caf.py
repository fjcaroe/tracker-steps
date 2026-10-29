from odoo.tests import TransactionCase, tagged

from .caf_cases import CAFCaseMixin


@tagged('post_install', '-at_install')
class TestCAFCore(CAFCaseMixin, TransactionCase):
    def test_core_has_no_parallel_model_or_counter(self):
        module = self.env['ir.module.module'].search([('name', '=', 'step_l10n_cl_edi_core')])
        self.assertEqual(module.license, 'LGPL-3')
        data = self.env['ir.model.data'].search([('module', '=', 'step_l10n_cl_edi_core')])
        self.assertFalse(data.filtered(lambda row: row.model in
            ('ir.model', 'ir.model.fields', 'ir.sequence', 'ir.model.access', 'ir.rule')))
