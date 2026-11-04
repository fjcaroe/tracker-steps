from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class BillOfMaterialsScopeCase(TransactionCase):

    def test_exact_company_scope_and_native_lookup(self):
        first = self.env.company
        second, excluded = self.env['res.company'].create([{'name': 'T157 A'}, {'name': 'T157 B'}])
        product = self.env['product.product'].create({'name': 'Producto T157'})
        model = self.env['mrp.bom'].with_context(allowed_company_ids=(first | second | excluded).ids)
        bom = model.create({
            'company_id': False, 'product_tmpl_id': product.product_tmpl_id.id,
            'step_applicable_company_ids': [Command.set((first | second).ids)],
        })
        self.assertEqual(model._bom_find(product, company_id=first.id)[product], bom)
        self.assertEqual(model._bom_find(product, company_id=second.id)[product], bom)
        self.assertFalse(model._bom_find(product, company_id=excluded.id)[product])
        with self.assertRaises(ValidationError):
            bom._check_step_bom_company(excluded)
