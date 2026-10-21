from datetime import date
from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class ShipmentCase(TransactionCase):
    def fixture(self):
        self.env = self.env(context=dict(self.env.context, tracking_disable=True,
            mail_create_nosubscribe=True, no_reset_password=True))
        self.season = self.env['step.temporada'].create({'name': 'QA T96 temporada'})
        self.species = self.env['step.especie'].create({'name': 'QA T96 cerezas', 'type_especie': 'frutal', 'group_especie': 'seco'})
        self.receiver = self.env['res.partner'].create({'name': 'QA T96 recibidor'})
        self.product = self.env['product.product'].create({'name': 'QA T96 caja', 'grupo_labor': 'pack'})
        pallet = self.env['stock.package.type'].create({'name': 'QA T96 pallet'})
        self.program = self.env['step.export.sales.program'].create({
            'name': 'QA T96 cerezas 2,5 kg', 'season_id': self.season.id, 'species_id': self.species.id,
            'partner_id': self.receiver.id, 'product_id': self.product.id, 'package_type_id': pallet.id,
            'date_start': date(2026, 10, 5), 'date_end': date(2026, 11, 30),
            'currency_id': self.env.ref('base.USD').id, 'rate_to_usd': 1,
            'pallets_per_container': 1, 'boxes_per_pallet': 10, 'kg_per_box': 10,
            'line_ids': [Command.create({'week_start': date(2026, 10, 5), 'container_qty': 1, 'price_per_kg': 6}),
                         Command.create({'week_start': date(2026, 11, 2), 'container_qty': 2, 'price_per_kg': 5})]})
        self.program.action_validate(); self.program.action_activate()
        self.shipment = self.env['step.export.export'].create({
            'name': 'QA T96 embarque', 'shipment_number': 'QA-T96-%s' % self.season.id, 'date': date(2026, 10, 7),
            'season_id': self.season.id, 'species_id': self.species.id, 'sales_program_id': self.program.id,
            'line_ids': [Command.create({'product_id': self.product.id, 'pallet_qty': 1,
                                        'boxes_per_pallet': 10, 'kg_per_box': 11.5})]})
        # Controlled test fixture: no dispatch, invoice, inventory move or DTE is emitted.
        self.shipment.line_ids.write({'kg_per_box': 10})
        self.second = self.env['product.product'].create({'name': 'QA otra carga', 'grupo_labor': 'pack'})
        self.env['step.export.shipment.line'].create({'shipment_id': self.shipment.id,
            'product_id': self.second.id, 'pallet_qty': 1, 'boxes_per_pallet': 10, 'kg_per_box': 30})
        self.shipment.state = 'shipped'

    def result(self, **filters):
        return self.program.dashboard_comparison({'season_id': self.season.id, **filters})

    def test_allocation_financial_currency_and_weighted_groups(self):
        company = self.env['res.company'].create({'name': 'QA T96 contabilidad',
            'country_id': False, 'currency_id': self.env.ref('base.USD').id})
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=[company.id]))
        self.fixture()
        accounts = self.env['account.account']
        income = accounts.create({'name': 'QA T96 ingreso', 'code': 'T96REV',
            'account_type': 'income', 'company_ids': [Command.set(company.ids)]})
        receivable = accounts.create({'name': 'QA T96 deudor', 'code': 'T96REC',
            'account_type': 'asset_receivable', 'reconcile': True, 'company_ids': [Command.set(company.ids)]})
        self.receiver.property_account_receivable_id = receivable
        journal = self.env['account.journal'].create({'name': 'QA T96 ventas', 'code': 'QT96',
            'type': 'sale', 'company_id': company.id, 'default_account_id': income.id,
            'l10n_latam_use_documents': False})
        usd, eur = self.env.ref('base.USD'), self.env.ref('base.EUR')
        eur.active = True
        self.env['res.currency.rate'].create({'currency_id': eur.id, 'company_id': company.id,
            'name': '2026-10-01', 'rate': 0.5})
        self.env['res.currency.rate'].create({'currency_id': usd.id, 'company_id': company.id,
            'name': '2026-10-01', 'rate': 1})
        def invoice(kind, amount, currency=usd, posted=True):
            move = self.env['account.move'].create({'move_type': kind, 'partner_id': self.receiver.id,
                'journal_id': journal.id, 'company_id': company.id, 'currency_id': currency.id,
                'invoice_date': '2026-10-07', 'date': '2026-10-07',
                'step_export_shipment_id': self.shipment.id,
                'invoice_line_ids': [Command.create({'name': 'QA T96 venta', 'quantity': 1,
                    'price_unit': amount, 'account_id': income.id, 'tax_ids': [Command.clear()]})]})
            if posted: move.action_post()
            return move
        invoice('out_invoice', 1000)
        invoice('out_invoice', 100)  # Debit notes are positive customer invoices in Odoo.
        invoice('out_refund', 50)
        invoice('out_invoice', 100, eur)
        invoice('out_invoice', 9000, posted=False)
        total = self.result()['species']['total']
        self.assertEqual(total['actual_usd'], 1250)
        self.assertAlmostEqual(total['actual_price'], 1250 / 400)

        self.env.flush_all()
        report = self.env['step.export.shipment.report']
        rows = report.search([('shipment_id', '=', self.shipment.id)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows.filtered(lambda r: r.product_id == self.product).amount_usd, 312.5)
        self.assertEqual(rows.filtered(lambda r: r.product_id == self.second).amount_usd, 937.5)
        grouped = report._read_group([('id', 'in', rows.ids)], [],
            ['amount_usd:sum', 'kg_qty:sum', 'price_per_kg:avg', 'shipment_count:sum'])[0]
        self.assertEqual(grouped, (1250, 400, 3.125, 1))
        legacy = report.read_group([('id', 'in', rows.ids)],
            ['amount_usd:sum', 'kg_qty:sum', 'price_per_kg:avg', 'shipment_count:sum'], [])[0]
        self.assertEqual(legacy['price_per_kg'], 3.125)
        self.assertEqual(legacy['shipment_count'], 1)
        self.assertEqual(rows[0].action_open_shipment()['res_id'], self.shipment.id)
        self.shipment = self.env['step.export.export'].create({'name':'QA sin kilos','shipment_number':'QA-NOKG','company_id':company.id})
        self.shipment.state='shipped'
        invoice('out_invoice',200)
        self.env.flush_all()
        missing = report.search([('shipment_id', '=', self.shipment.id)])
        self.assertTrue(missing.allocation_missing)
        self.assertEqual(missing.amount_usd, 200)


@tagged('post_install', '-at_install')
class PackingCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.location = cls.warehouse.lot_stock_id
        cls.producer = cls.env["res.partner"].create({"name": "Productor Packing T41"})
        cls.species = cls.env["step.especie"].create({
            "name": "Cereza Packing T41", "type_especie": "frutal", "group_especie": "fruta_h"})
        cls.variety_group = cls.env["step.grupo.variedad"].create({
            "name": "Grupo T41", "especie_id": cls.species.id})
        cls.variety = cls.env["step.variedad"].create({
            "name": "Santina T41", "cod_variedad": "T41S", "especie_id": cls.species.id,
            "grupo_variedad_id": cls.variety_group.id})
        cls.raw = cls.env["product.product"].create({
            "name": "Fruta granel T41", "is_storable": True, "weight": 1.0, "grupo_labor": "pack"})
        cls.finished = cls.env["product.product"].create({
            "name": "Caja exportación T41", "default_code": "T41-EXPORT", "is_storable": True, "weight": 5.0, "grupo_labor": "pack"})
        cls.national = cls.env["product.product"].create({
            "name": "Fruta nacional T41", "is_storable": True, "weight": 1.0, "grupo_labor": "pack"})
        cls.carton = cls.env["product.product"].create({
            "name": "Cartón T41", "is_storable": True, "grupo_labor": "pack"})

    def _tag(self, name, kind, product, kilos, boxes, result=False, fruit_type=False):
        return self.env["stock.quant.package"].create({
            "name": name, "is_fruit_tag": True, "step_tag_kind": kind, "fruit_type": fruit_type,
            "step_packing_result": result, "step_producer_id": self.producer.id,
            "especie_id": self.species.id, "variedad_id": self.variety.id,
            "step_tag_line_ids": [(0, 0, {
                "producer_id": self.producer.id, "product_id": product.id,
                "quantity": boxes, "boxes": boxes, "kilos": kilos,
            })],
        })

    def _stock(self, product, qty, package=False):
        self.env["stock.quant"]._update_available_quantity(product, self.location, qty, package_id=package or None)

    def test_real_close_standard_snapshot_and_comparisons(self):
        line = self.env['step.packing.line'].create({'name':'QA T99 linea', 'company_id':self.company.id})
        standard = self.env['step.packing.line.standard'].create({'line_id':line.id, 'species_id':self.species.id, 'kg_hour':40})
        incoming = self._tag('T41-R2-C', 'C', self.raw, 100, 100)
        incoming.action_step_validate_tag()
        self._stock(self.raw, 100, incoming)
        ot = self.env['step.packing.production'].create({
            'raw_product_id': self.raw.id, 'fruit_grower_id': self.producer.id,
            'step_packing_line_id':line.id, 'date':'2026-11-09',
            'started_at':'2026-11-09 08:00:00', 'finished_at':'2026-11-09 10:00:00',
            'fruit_species_id': self.species.id, 'fruit_variety_id': self.variety.id,
            'step_packing_input_tag_ids': [(6, 0, incoming.ids)]})
        action = ot.action_create_export_tag()
        self.assertEqual(action['context']['default_step_packing_production_id'], ot.id)
        export = self._tag('T41-R2-E', 'E', self.finished, 80, 16, 'export')
        national = self._tag('T41-R2-N', 'N', self.national, 15, 15, 'commercial')
        ot.step_packing_output_tag_ids = export | national
        self.env['mrp.bom'].create({'product_tmpl_id': self.finished.product_tmpl_id.id,
            'product_qty': 1, 'bom_line_ids': [(0, 0, {'product_id': self.carton.id, 'product_qty': 1, 'step_export_qty_per_pallet': 2})]})
        self._stock(self.carton, 18)
        ot.action_step_packing_validate()
        ot.action_prepare_materials()
        self.assertEqual(ot.material_line_ids.quantity, 18)
        ot.action_approve_materials()
        ot.action_step_packing_close()
        self.assertFalse(ot.product_id)
        self.assertEqual(ot.state, 'closed')
        self.assertEqual(ot.step_packing_loss_kg, 5)
        self.assertEqual(set(ot.output_picking_id.move_ids.product_id.ids), {self.finished.id, self.national.id})
        self.assertEqual(national.quant_ids.owner_id, self.producer)

        standard.kg_hour = 60
        self.assertEqual(ot.standard_kg_hour, 40)
        result = self.env['step.packing.order'].operational_comparison('packing',
            {'species_id':self.species.id, 'month':'2026-11', 'week':'2026-11-09'})
        process, machine = [table['total'] for table in result['tables']]
        self.assertEqual((process['input'], process['export'], process['loss']), (100,80,5))
        self.assertEqual((process['export_percent'],process['loss_percent']), (80,5))
        self.assertEqual((machine['hours'], machine['actual_rate'], machine['standard_rate'],machine['variation']), (2,50,40,25))
        producer = self.env['step.packing.order'].operational_comparison('producers', {'species_id':self.species.id})
        self.assertEqual(producer['tables'][0]['total']['actual'],80)
        self.assertIsNone(producer['tables'][0]['total']['variation'])
        self.assertFalse(self.env['step.packing.order'].operational_comparison('packing',
            {'species_id':self.species.id,'month':'2027-01'})['tables'][0]['rows'])
        with self.assertRaises(ValidationError):
            self.env['step.packing.order'].operational_comparison('packing',{'week':'2026-11-10'})

    def test_weighted_missing_hours_and_baselines(self):
        rows=[]
        for kg,hours,rate in ((100,2,40),(300,3,60),(50,0,0)):
            rows.append(dict(species=self.species,line=self.env['step.packing.line'],
                input=kg,export=kg*.8,commercial=0,precaliber=0,waste=0,loss=kg*.2,
                hours=hours,standard=rate))
        totals=self.env['step.packing.order']._packing_tables(rows)
        machine=totals[1]['total']
        self.assertEqual((machine['input'],machine['hours'],machine['actual_rate'],machine['standard_rate'],machine['missing_hours']), (400,5,80,52,1))
        rows[0]['standard']=0
        self.assertIsNone(self.env['step.packing.order']._packing_tables(rows)[1]['total']['standard_rate'])


@tagged('post_install', '-at_install')
class ProducerCase(TransactionCase):
    def sample(self, group='bins', kind='process'):
        env = self.env(context=dict(self.env.context, no_reset_password=True,
                                   tracking_disable=True, mail_create_nosubscribe=True))
        producer = env['res.partner'].create({'name':'QA T75 producer','is_productor':True})
        packing = env['res.partner'].create({'name':'QA T75 packing','step_export_packing':True})
        fundo = env['step.fundo'].create({'name':'QA T75 farm','partner_id':producer.id})
        season = env['step.temporada'].create({'name':'QA T75 season'})
        species = env['step.especie'].create({'name':'QA T75 species','type_especie':'frutal',
            'group_especie':'baya','kg_caja':5,'base_boxes_per_pallet':200})
        product = env['product.product'].create({'name':'QA T75 fruit','is_fruta':True})
        package = env['stock.package.type'].create({'name':'QA T74 package',
            'fruit_package_group':group,'step_export_boxes_per_pallet':35,'pallets_per_aircraft':4})
        estimate = env['step.export.estimate'].create({'name':'QA T75 estimate','producer_id':producer.id,
            'packing_partner_id':packing.id,'fundo_id':fundo.id,'season_id':season.id,
            'estimate_line_ids':[Command.create({'species_id':species.id,'product_id':product.id,
                'package_type_id':package.id,'delivery_kind':kind,'export_kg':100000,
                'export_percentage':.8,'kg_per_box':9,'boxes_per_package':999,
                'week_line_ids':[Command.create({'week_start':'2026-11-02','export_kg':40000}),
                                 Command.create({'week_start':'2026-11-09','export_kg':60000})]})]})
        return estimate

    def test_estimate_version_and_real_packed_receipt(self):
        estimate=self.sample()
        estimate.action_validate_estimate(); estimate.action_activate_estimate()
        line=estimate.estimate_line_ids
        species=line.species_id
        warehouse=self.env['stock.warehouse'].search([('company_id','=',self.env.company.id)],limit=1)
        product=self.env['product.product'].create({'name':'QA T98 caja', 'is_storable':True,'weight':5,'grupo_labor':'pack'})
        tag=self.env['stock.quant.package'].create({'name':'QA T98 recepcion', 'is_fruit_tag':True,'step_tag_kind':'E'})
        picking=self.env['stock.picking'].create({'partner_id':estimate.producer_id.id,
            'picking_type_id':warehouse.in_type_id.id, 'location_id':warehouse.in_type_id.default_location_src_id.id,
            'location_dest_id':warehouse.lot_stock_id.id,'step_fruit_reception_kind':'packed',
            'fruit_fundo_id':estimate.fundo_id.id,'fruit_species_id':species.id,
            'fruit_season_id':estimate.season_id.id,'step_fruit_gross_kg':50,
            'fruit_tag_line_ids':[Command.create({'tag_number':tag.name,'package_id':tag.id,
                'product_id':product.id,'quantity':10,'kilos':50,'box_count':10})]})
        order=self.env['step.packing.order']
        filters={'species_id':species.id,'season_id':estimate.season_id.id}
        self.assertEqual(order.operational_comparison('producers',filters)['tables'][0]['total']['actual'],0)
        picking.action_prepare_fruit_stock(); picking.button_validate()
        self.assertEqual(picking.state,'done')
        result=order.operational_comparison('producers',filters)
        for table in result['tables']:
            total=table['total']
            self.assertEqual((total['estimated'],total['actual'],total['difference']), (100000,50,-99950))
            self.assertEqual(total['variation'],-99.95)
        self.assertEqual(order.operational_comparison('producers',dict(filters,month='2026-11',week='2026-11-02'))['tables'][0]['total']['estimated'],40000)
        replacement=self.env[estimate._name].browse(estimate.action_new_estimate_version()['res_id'])
        replacement.estimate_line_ids.week_line_ids[0].export_kg=50000
        replacement.estimate_line_ids.export_kg=110000
        replacement.action_validate_estimate(); replacement.action_activate_estimate()
        self.assertEqual(order.operational_comparison('producers',filters)['tables'][0]['total']['estimated'],110000)
        other=self.env['res.company'].create({'name':'QA T98 otra empresa','country_id':False})
        self.assertFalse(order.with_context(allowed_company_ids=other.ids).operational_comparison('producers',filters)['tables'][0]['rows'])
