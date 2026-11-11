from datetime import date

from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class DashboardCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if 'step_packing_warehouse_id' in cls.company._fields:
            cls.company.write({'step_packing_warehouse_id': False, 'step_packing_fruit_location_id': False,
                               'step_packing_material_location_id': False})
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.location = cls.warehouse.lot_stock_id
        cls.producer = cls.env['res.partner'].create({'name': 'QA T201 productor'})
        cls.species = cls.env['step.especie'].create({'name': 'QA T201 especie', 'type_especie': 'frutal', 'group_especie': 'fruta_h'})
        group = cls.env['step.grupo.variedad'].create({'name': 'QA T201 grupo', 'especie_id': cls.species.id})
        cls.variety = cls.env['step.variedad'].create({'name': 'QA T201 variedad', 'cod_variedad': 'T201',
            'especie_id': cls.species.id, 'grupo_variedad_id': group.id})
        cls.raw = cls.env['product.product'].create({'name': 'QA T201 granel', 'is_storable': True, 'weight': 1, 'grupo_labor': 'pack'})
        cls.finished = cls.env['product.product'].create({'name': 'QA T201 exportación', 'is_storable': True, 'weight': 5, 'grupo_labor': 'pack'})
        cls.carton = cls.env['product.product'].create({'name': 'QA T201 cartón', 'is_storable': True, 'grupo_labor': 'pack'})
        cls.dashboard = cls.env['step.packing.order']

    def tag(self, kilos=100, kind='C', state='validated', day='2001-06-10', company=None):
        company = company or self.company
        tag = self.env['stock.quant.package'].with_company(company).create({
            'is_fruit_tag': True, 'step_tag_kind': kind, 'company_id': company.id,
            'step_packing_result': 'export' if kind == 'E' else False,
            'step_producer_id': self.producer.id, 'especie_id': self.species.id,
            'variedad_id': self.variety.id, 'received_at': day + ' 12:00:00',
            'step_tag_line_ids': [Command.create({'producer_id': self.producer.id,
                'product_id': self.finished.id if kind == 'E' else self.raw.id,
                'quantity': kilos / 5 if kind == 'E' else kilos,
                'boxes': kilos / 5 if kind == 'E' else kilos, 'kilos': kilos})]})
        if state == 'validated':
            tag.action_step_validate_tag()
        elif state != 'created':
            tag.step_tag_state = state
        return tag

    def panel(self, **kwargs):
        values = dict(period='custom', date_from='2001-06-01', date_to='2001-06-30', species_id=self.species.id)
        values.update(kwargs)
        return self.dashboard.get_dashboard_data(**values)

    def test_seven_metrics_use_real_kilos_exclude_drafts_void_and_national(self):
        raw = self.tag(150)
        self.tag(80, 'E')
        self.tag(999, state='created')
        self.tag(888, state='void')
        self.tag(777, kind='N')
        result = self.panel()
        self.assertEqual([result['kpis'][key] for key in ('open_productions', 'received_kg',
            'processed_kg', 'stock_input_kg', 'export_kg', 'shipped_kg', 'stock_export_kg')], [0,150,0,150,80,0,80])
        self.assertEqual(result['actions']['received_kg']['domain'], [('id', 'in', raw.ids)])

    def test_date_bounds_and_empty_result(self):
        self.tag(10, day='2001-06-01')
        self.tag(20, day='2001-06-30')
        self.tag(99, day='2001-07-01')
        self.assertEqual(self.panel()['kpis']['received_kg'], 30)
        self.assertEqual(self.panel(date_from='2000-01-01', date_to='2000-01-31')['kpis']['received_kg'], 0)

    def test_active_company_not_union_of_checked_companies(self):
        other = self.env['res.company'].create({'name': 'QA T201 otra empresa'})
        own = self.tag(25)
        foreign = self.tag(900, company=other)
        result = self.dashboard.with_context(allowed_company_ids=[self.company.id, other.id]).get_dashboard_data(
            period='custom', date_from='2001-06-01', date_to='2001-06-30', species_id=self.species.id)
        self.assertEqual(result['kpis']['received_kg'], 25)
        self.assertEqual(result['actions']['received_kg']['domain'], [('id', 'in', own.ids)])
        self.assertNotEqual(own.company_id, foreign.company_id)

    def test_receipt_utc_is_compared_in_user_timezone(self):
        tag = self.tag(10, state='created')
        tag.received_at = '2001-06-01 02:00:00'
        tag.action_step_validate_tag()
        panel = self.dashboard.with_context(tz='America/Santiago').get_dashboard_data(
            period='custom', date_from='2001-06-01', date_to='2001-06-30', species_id=self.species.id)
        self.assertEqual(panel['kpis']['received_kg'], 0)

    def test_bad_filters_are_rejected(self):
        for kwargs in ({'period':'invalid'}, {'date_from':'no'}, {'date_from':'2001-07-01'},
                       {'date_to':False}, {'species_id':'x'}):
            with self.assertRaises(ValidationError):
                self.panel(**kwargs)

    def test_period_presets_and_season(self):
        self.tag(10)
        day = self.dashboard.get_dashboard_data('day')['filters']
        anchor = date.fromisoformat(day['date_from'])
        self.assertEqual(day['date_from'], day['date_to'])
        week = self.dashboard.get_dashboard_data('week')['filters']
        self.assertEqual(date.fromisoformat(week['date_from']).weekday(), 0)
        self.assertEqual((date.fromisoformat(week['date_to']) - date.fromisoformat(week['date_from'])).days, 6)
        self.assertEqual(self.dashboard.get_dashboard_data('month')['filters']['date_from'], anchor.replace(day=1).isoformat())
        self.env['step.temporada'].create({'name':'QA T201 temporada', 'start_date':anchor.replace(month=1,day=1),
            'end_date':anchor.replace(month=12,day=31), 'company_ids':[Command.set(self.company.ids)]})
        self.assertTrue(self.dashboard.get_dashboard_data('season')['filters']['date_from'])

    def test_open_orders_and_recent_rows_apply_date_and_species(self):
        self.tag(10)
        current = self.env['step.packing.production'].create({'date':'2001-06-10', 'fruit_species_id':self.species.id})
        self.env['step.packing.production'].create({'date':'2000-06-10', 'fruit_species_id':self.species.id})
        result = self.panel()
        self.assertEqual(result['kpis']['open_productions'], 1)
        self.assertEqual([p['id'] for p in result['recent_productions']], current.ids)

    def test_real_repack_does_not_double_receipts(self):
        source = self.tag(100)
        self.env['stock.quant']._update_available_quantity(self.raw, self.location, 100, package_id=source)
        targets = self.env['stock.quant.package']
        for index in range(2):
            targets |= targets.create({'is_fruit_tag':True, 'step_tag_kind':'C',
                'especie_id':self.species.id,'variedad_id':self.variety.id,'step_producer_id':self.producer.id})
        repack = self.env['step.packing.repack'].create({'line_ids': [Command.create({
            'source_package_id':source.id, 'target_package_id':target.id, 'producer_id':self.producer.id,
            'product_id':self.raw.id, 'quantity':qty, 'boxes':qty, 'kilos':qty})
            for target,qty in zip(targets,[60,40])]})
        repack.action_validate()
        result = self.panel()
        self.assertEqual(source.step_tag_state, 'repalletized')
        self.assertEqual(result['kpis']['received_kg'],100)
        self.assertEqual(result['kpis']['stock_input_kg'],100)
        self.assertEqual(set(result['actions']['stock_input_kg']['domain'][0][2]),set(targets.ids))

    def test_real_close_and_dispatch_keep_event_dates(self):
        incoming = self.tag(100)
        self.env['stock.quant']._update_available_quantity(self.raw, self.location, 100, package_id=incoming)
        ot = self.env['step.packing.production'].create({'date':'2001-06-15', 'raw_product_id':self.raw.id,
            'fruit_grower_id':self.producer.id, 'fruit_species_id':self.species.id,
            'fruit_variety_id':self.variety.id,'step_packing_input_tag_ids':[Command.set(incoming.ids)]})
        export = self.tag(80,'E',state='created')
        ot.step_packing_output_tag_ids = export
        self.env['mrp.bom'].create({'product_tmpl_id':self.finished.product_tmpl_id.id,
            'product_qty':1,'bom_line_ids':[Command.create({'product_id':self.carton.id,'product_qty':1})]})
        self.env['stock.quant']._update_available_quantity(self.carton,self.location,20)
        ot.action_step_packing_validate()
        ot.action_prepare_materials()
        ot.action_approve_materials()
        ot.action_step_packing_close()
        result = self.panel()
        self.assertEqual([result['kpis'][k] for k in ('received_kg','processed_kg','stock_input_kg','export_kg','stock_export_kg')],[100,100,0,80,80])
        self.assertEqual(self.panel(date_from='2001-06-15',date_to='2001-06-15')['kpis']['processed_kg'],100)
        self.assertEqual(self.panel(date_from='2001-06-10',date_to='2001-06-10')['kpis']['processed_kg'],0)
        from odoo.addons.step_packing_operations.models.material_tools import create_stock_transfer
        destination = self.producer.with_company(self.company).property_stock_customer
        picking = create_stock_transfer(ot,self.warehouse,self.location,destination,[(self.finished,16,export,False)])
        picking.move_line_ids.write({'date':'2001-06-20 12:00:00'})
        export.step_tag_state = 'dispatched'
        self.assertEqual(self.panel()['kpis']['shipped_kg'],80)
        self.assertEqual(self.panel()['kpis']['stock_export_kg'],0)
        self.assertEqual(self.panel(date_from='2001-06-10',date_to='2001-06-19')['kpis']['shipped_kg'],0)
        export.step_tag_state = 'liquidated'
        self.assertEqual(self.panel()['kpis']['shipped_kg'],80)

    def test_missing_shipment_date_is_explicit_and_readonly(self):
        tag = self.tag(50,'E',state='dispatched')
        before = tag.read(['step_tag_state','write_date','step_actual_kg'])
        result = self.panel()
        self.assertGreaterEqual(result['undated_shipments'],1)
        self.assertEqual(result['kpis']['shipped_kg'],0)
        self.assertEqual(tag.read(['step_tag_state','write_date','step_actual_kg']),before)
