from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class PackingFolioCase(TransactionCase):

    def test_duplicate_guard_and_historical_detached_report_row(self):
        producer = self.env['res.partner'].create({'name': 'Productor QA T162'})
        product = self.env['product.product'].create({'name': 'Producto QA T162'})
        order = self.env['step.packing.production'].create({})
        model = self.env['stock.quant.package']

        def create_tag(folio):
            return model.create({
                'name': folio, 'is_fruit_tag': True, 'step_tag_kind': 'E',
                'step_packing_result': 'export', 'step_producer_id': producer.id,
                'step_packing_production_id': order.id,
                'step_tag_line_ids': [Command.create({
                    'producer_id': producer.id, 'product_id': product.id,
                    'quantity': 10, 'boxes': 10, 'kilos': 15,
                })],
            })

        canonical = create_tag('QA-T162')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            create_tag('qa-t162')
        detached = create_tag('QA-T162-LEGACY')
        order.step_packing_output_tag_ids = [Command.unlink(detached.id)]
        detached.flush_recordset(['name', 'step_packing_folio_key'])
        self.cr.execute("UPDATE stock_quant_package SET name=%s, step_packing_folio_key=NULL WHERE id=%s",
                        [canonical.name, detached.id])
        detached.invalidate_recordset(['name', 'step_packing_folio_key'], flush=False)
        self.assertEqual(order.step_packing_output_tag_ids, canonical)
        self.assertEqual(model.search([('id', 'in', (canonical | detached).ids),
                                       ('step_packing_detached_duplicate', '=', False)]), canonical)
        self.assertTrue(detached.exists())
