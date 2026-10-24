from lxml import etree
from odoo.tests import TransactionCase, Form, tagged


@tagged('post_install', '-at_install')
class TareCase(TransactionCase):
    def test_packaging_form_persists_two_decimals_and_relations(self):
        model = self.env['product.packaging']
        packaging = model.search([], limit=1)
        self.assertTrue(packaging)
        original = packaging.read(['product_id', 'qty', 'step_export_kg_per_box'])[0]
        with Form(packaging, view='step_export.view_step_export_packaging_form') as form:
            form.step_tare_weight = 1.27
        self.env.flush_all()
        packaging.invalidate_recordset()
        self.assertEqual(packaging.step_tare_weight, 1.27)
        self.assertEqual(packaging.read(list(original.keys() - {'id'}))[0], original)
        self.assertEqual(model._fields['step_tare_weight'].digits, (16, 2))

    def test_pallet_form_uses_existing_native_weight(self):
        model = self.env['stock.package.type']
        pallet = model.search([], limit=1)
        self.assertTrue(pallet)
        original = pallet.read(['step_export_boxes_per_pallet', 'max_weight'])[0]
        with Form(pallet, view='step_export.view_step_export_package_type_form') as form:
            form.base_weight = 22.35
        self.env.flush_all()
        pallet.invalidate_recordset()
        self.assertEqual(pallet.base_weight, 22.35)
        self.assertEqual(pallet.read(list(original.keys() - {'id'}))[0], original)
        self.assertEqual(model._fields['base_weight'].digits, (16, 2))
        arch = etree.fromstring(model.get_view(
            view_id=self.env.ref('step_export.view_step_export_package_type_form').id,
            view_type='form')['arch'])
        self.assertEqual(arch.xpath("//field[@name='base_weight']/@string"), ['Tara de pallet'])
