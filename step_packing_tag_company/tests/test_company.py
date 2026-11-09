from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
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

    def test_manual_fruit_tag_keeps_company_before_stock(self):
        model = self.env['stock.quant.package']
        tag = model.create({'is_fruit_tag': True, 'step_tag_kind': 'C', 'company_id': False})
        self.env.add_to_compute(tag._fields['company_id'], tag)
        tag._recompute_recordset(['company_id'])
        self.assertEqual(tag.company_id, self.env.company)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            tag.write({'company_id': False})

    def test_confirmed_duplicate_is_retained_and_removed_from_tag_reports(self):
        model = self.env['stock.quant.package']
        duplicate = self.make_tag('E')
        order = duplicate.step_packing_production_id
        valid = model.create({
            'is_fruit_tag': True, 'step_tag_kind': 'E', 'step_packing_result': 'export',
            'step_packing_production_id': order.id,
        })
        duplicate.write({'step_tag_state': 'void', 'step_packing_duplicate_of_id': valid.id})
        for xml_id in ('step_packing_ticket_revision.tags', 'step_inventory_packing.action_steps_fruit_packages'):
            report_domain = safe_eval(self.env.ref(xml_id).domain)
            self.assertEqual(model.search([('id', 'in', (valid | duplicate).ids), *report_domain]), valid)
        self.assertTrue(duplicate.exists())
