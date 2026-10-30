from odoo.tests import TransactionCase, tagged
from odoo.addons.step_packing_tag_company.hooks import post_init_hook


@tagged('post_install', '-at_install')
class CompanyCase(TransactionCase):
    def make_tag(self, kind):
        ot = self.env['step.packing.production'].create({'company_id': self.env.company.id})
        return self.env['stock.quant.package'].create({
            'is_fruit_tag': True, 'step_tag_kind': kind,
            'step_packing_result': 'export' if kind == 'E' else 'commercial',
            'step_packing_production_id': ot.id})

    def test_export_and_national_without_stock_have_origin_company(self):
        for kind in ('E', 'N'):
            tag = self.make_tag(kind)
            self.assertEqual(tag.company_id, tag.step_packing_production_id.company_id)
            self.assertFalse(tag.quant_ids)
            self.env.flush_all()
            self.env.invalidate_all()
            self.assertEqual(tag.company_id, self.env.company)
            self.assertIn(tag, self.env['stock.quant.package'].search([('company_id', '=', self.env.company.id)]))

    def test_backfill_preserves_location_and_state(self):
        tag = self.make_tag('E')
        location = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1).lot_stock_id
        self.env.cr.execute('UPDATE stock_quant_package SET company_id=NULL, location_id=%s WHERE id=%s', [location.id, tag.id])
        tag.invalidate_recordset()
        before = tag.read(['location_id', 'step_tag_state', 'step_packing_production_id', 'write_date'])
        post_init_hook(self.env)
        self.assertEqual(tag.company_id, self.env.company)
        self.assertEqual(tag.read(['location_id', 'step_tag_state', 'step_packing_production_id', 'write_date']), before)

    def test_unrelated_empty_package_keeps_native_company(self):
        tag = self.env['stock.quant.package'].create({})
        self.assertFalse(tag.company_id)
