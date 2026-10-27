from odoo.tests import TransactionCase,tagged,Form
from odoo.addons.step_agriculture_format_core.hooks import pre_init_hook,post_init_hook
from odoo.addons.step_agriculture_format_core.ownership import RECORDS

@tagged('post_install','-at_install')
class AgricultureFormatCase(TransactionCase):
    def test_native_packaging_and_aliases_preserve_links(self):
        for key in RECORDS:
            self.assertEqual(self.env.ref('step_export.'+key),self.env.ref('step_agriculture_format_core.'+key))
        product=self.env['product.product'].create({'name':'Private format fruit','grupo_labor':'pack'})
        with Form(self.env['product.packaging'],view='step_export.view_step_export_packaging_form') as form:
            form.name='Private shared packaging';form.product_id=product;form.qty=12;form.step_export_kg_per_box=8.125
        package=form.record
        self.assertEqual(package.product_id,product)
        self.assertEqual(package.qty,12);self.assertEqual(package.step_export_kg_per_box,8.125)
        before=package.read()[0]
        ids={stem:self.env.ref('step_export.action_step_export_'+stem).view_ids.ids for stem in ('packaging','package_type')}
        pre_init_hook(self.env);post_init_hook(self.env)
        self.assertEqual(package.read()[0],before)
        for stem in ids:
            self.assertEqual(self.env.ref('step_export.action_step_export_'+stem).view_ids.ids,ids[stem])

    def test_native_pallet_capacity_form(self):
        with Form(self.env['stock.package.type'],view='step_export.view_step_export_package_type_form') as form:
            form.name='Private pallet';form.step_export_boxes_per_pallet=30
            form.step_export_pallets_20=8;form.step_export_pallets_40=20
        pallet=form.record
        self.assertEqual(pallet.step_export_pallets_40,20)
        self.assertEqual(pallet.step_export_boxes_per_pallet,30)
