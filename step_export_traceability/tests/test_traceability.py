from lxml import etree
from odoo.tests import tagged
from odoo.addons.step_packing_sag.tests.test_sag import SagCase


@tagged('post_install', '-at_install', 'step_export_traceability')
class TraceCase(SagCase):
    def test_complete_panel_links_and_native_action(self):
        inspection, shipment = self._closed()
        tag = inspection.package_ids
        production = inspection.production_id
        source = production.step_packing_input_tag_ids
        # Bind a native reception to the actual source pallet.
        receipt = self.env['stock.picking'].create({
            'picking_type_id':self.warehouse.in_type_id.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': self.location.id,
            'fruit_lot':'LOTE T94', 'fruit_guide_number':'GUIA T94',
            'step_fruit_cost_center':'Cuartel histórico T94',
            'fruit_tag_line_ids':[(0,0,{'tag_number':'ORIGEN T94','package_id':source.id})]})
        shipment.write({'receiver_id':self.producer.id, 'departure_date':'2026-10-20',
                        'arrival_date':'2026-11-01', 'bl_folio':'BL T94'})
        self.producer.name = '<script>QA T94</script>'
        g = tag._trace_graph()
        self.assertIn(production, g['productions'])
        self.assertIn(source, g['tags'])
        self.assertIn(receipt, g['receipts'])
        self.assertIn(shipment, g['shipments'])
        self.assertIn(inspection, g['inspections'])
        tag._compute_trace()
        html = str(tag.trace_panel)
        tree = etree.HTML(html)
        self.assertEqual(len(tree.xpath('//section')),7)
        self.assertIn('LOTE T94',html)
        self.assertIn('GUIA T94',html)
        self.assertIn('Cuartel histórico T94',html)
        self.assertIn('BL T94',html)
        from odoo.tools import format_date
        self.assertIn(format_date(self.env,shipment.arrival_date),html)
        self.assertIn('model=step.packing.production',html)
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn(production.name,tag.trace_process)
        self.assertIn('LOTE T94',tag.trace_reception)
        action = self.env.ref('step_export.action_export_traceability')
        self.assertEqual(action.res_model,'stock.quant.package')
        self.assertEqual(action.view_id,self.env.ref('step_export_traceability.view_traceability_list'))
        for name in ('view_traceability_form','view_traceability_list','view_traceability_search'):
            view=self.env.ref('step_export_traceability.'+name)
            self.env['stock.quant.package'].get_view(view_id=view.id,view_type=view.type)

    def test_empty_and_live_refresh(self):
        self._fixture()
        tag = self._tag('T94 EMPTY', 'E', self.finished, 50,10,'export')
        tag._compute_trace()
        self.assertIn('Sin registro',str(tag.trace_panel))
        self.assertIn('Número proceso / OT: Sin registro',tag.trace_process)
        self.assertIn('Número recepción: Sin registro',tag.trace_reception)
        ship=self.env['step.export.export'].create({'name':'NUEVO T94','tag_ids':[(6,0,tag.ids)]})
        tag.invalidate_recordset()
        self.assertIn(ship.shipment_number,tag.trace_export)
        # A query never changes package lifecycle or creates evidence.
        self.assertEqual(tag.step_tag_state,'created')
        self.assertFalse(tag._trace_graph()['inspections'])

    def test_repack_retains_prior_process_and_company_rules(self):
        inspection, _ = self._closed()
        source = inspection.package_ids
        production = inspection.production_id
        repack = self.env['step.packing.repack'].create({'selected_source_ids':[(6,0,source.ids)]})
        repack.action_prepare_distribution()
        target = repack.line_ids.target_package_id
        # Draft repacks cannot create asserted genealogy.
        self.assertNotIn(source,target._trace_graph()['tags'])
        repack.action_validate()
        graph=target._trace_graph()
        self.assertIn(source,graph['tags'])
        self.assertIn(production,graph['productions'])
        self.assertIn(repack,graph['repacks'])
        from odoo.tests.common import new_test_user
        from odoo.exceptions import AccessError
        foreign=self.env['res.company'].create({'name':'Otra empresa T94'})
        user=new_test_user(self.env,login='t94-stock',groups='stock.group_stock_user',
                          company_id=foreign.id,company_ids=[(6,0,foreign.ids)])
        with self.assertRaises(AccessError):
            source.with_user(user)._trace_graph()
