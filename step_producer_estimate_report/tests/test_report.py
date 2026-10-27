from datetime import date, timedelta
from odoo import Command
from odoo.tests.common import TransactionCase, new_test_user
from odoo.exceptions import AccessError
from lxml import etree

class EstimateReportCase(TransactionCase):
    def test_community_calendar_keeps_week_and_original_view_id(self):
        action = self.env.ref('step_producer_estimate_report.report_action')
        view = self.env.ref('step_producer_estimate_report.report_gantt')
        self.assertEqual(action.view_mode, 'calendar,pivot,list')
        self.assertEqual(action.view_ids[0].view_id, view)
        arch = etree.fromstring(self.env['step.producer.estimate.report'].get_view(view.id, 'calendar')['arch'])
        self.assertEqual((arch.tag, arch.get('date_start'), arch.get('date_stop')),
                         ('calendar', 'week_start', 'calendar_end'))
        self.assertTrue(all(arch.get(flag) == 'false' for flag in ('create', 'edit', 'delete', 'quick_create')))
        estimate, _price = self.sample()
        rows = self.env['step.producer.estimate.report'].search([('estimate_id', '=', estimate.id)])
        self.assertTrue(all(row.calendar_end == row.week_start + timedelta(days=6) for row in rows))
        next_week = self.env['step.producer.estimate.report'].search([
            ('estimate_id', '=', estimate.id), ('calendar_end', '>=', date(2026, 11, 9))])
        self.assertEqual(next_week.week_start, date(2026, 11, 9))

    def sample(self):
        env=self.env
        producer=env['res.partner'].create({'name':'QA T68 producer','is_productor':True})
        packing=env['res.partner'].create({'name':'QA T68 packing','step_export_packing':True})
        fundo=env['step.fundo'].create({'name':'QA T68 farm','partner_id':producer.id})
        season=env['step.temporada'].create({'name':'QA T68 season'})
        species=env['step.especie'].create({'name':'QA T68 fruit','type_especie':'frutal','group_especie':'seco'})
        group=env['step.grupo.variedad'].create({'name':'QA T68 group','especie_id':species.id})
        variety=env['step.variedad'].create({'name':'QA T68 variety','cod_variedad':'QA-T68','especie_id':species.id,'grupo_variedad_id':group.id})
        product=env['product.product'].create({'name':'QA T68 fruit','is_fruta':True,'grupo_labor':'pack'})
        estimate=env['step.export.estimate'].create({'name':'QA T68 estimate','producer_id':producer.id,'packing_partner_id':packing.id,
            'fundo_id':fundo.id,'season_id':season.id,'delivery_start':date(2026,11,2),'delivery_end':date(2026,11,15),
            'estimate_line_ids':[Command.create({'species_id':species.id,'variety_id':variety.id,'product_id':product.id,
                'export_kg':100,'export_percentage':0.8,'kg_per_box':5,'boxes_per_package':10,
                'week_line_ids':[Command.create({'week_start':date(2026,11,2),'export_kg':40}),Command.create({'week_start':date(2026,11,9),'export_kg':60})]})]})
        price=env['step.producer.preliq.price'].create({'name':'QA T68 price','season_id':season.id,'species_id':species.id,
            'valid_from':date(2026,11,1),'valid_to':date(2026,11,30),'currency_id':env.ref('base.USD').id,
            'line_ids':[Command.create({'variety_id':variety.id,'uom_id':env.ref('uom.product_uom_kgm').id,'price':2})]})
        env.flush_all()
        return estimate,price

    def test_live_weekly_quantities_and_value(self):
        estimate,price=self.sample()
        report=self.env['step.producer.estimate.report'].search([('estimate_id','=',estimate.id)])
        self.assertEqual(len(report),2)
        self.assertAlmostEqual(sum(report.mapped('process_kg')),125)
        self.assertAlmostEqual(sum(report.mapped('export_box_qty')),20)
        self.assertAlmostEqual(sum(report.mapped('export_pallet_qty')),2)
        self.assertAlmostEqual(sum(report.mapped('bin_qty')),2.5)
        self.assertAlmostEqual(sum(report.mapped('amount_usd')),200)
        self.assertEqual(set(report.mapped('valuation_status')),{'valued'})
        price.line_ids.price=3;self.env.flush_all();report.invalidate_recordset()
        self.assertAlmostEqual(sum(report.mapped('amount_usd')),300)
        estimate.estimate_line_ids.week_line_ids[0].export_kg=30
        self.env.flush_all();report.invalidate_recordset()
        self.assertEqual(sum(report.mapped('export_kg')),90)

    def test_missing_and_ambiguous_prices_are_flagged(self):
        estimate,price=self.sample()
        report=self.env['step.producer.estimate.report'].search([('estimate_id','=',estimate.id)])
        price.line_ids.copy();self.env.flush_all();report.invalidate_recordset()
        self.assertEqual(set(report.mapped('valuation_status')),{'ambiguous'})
        self.assertEqual(sum(report.mapped('unvalued_week_qty')),2)
        self.assertFalse(any(report.mapped('amount_usd')))
        price.active=False;self.env.flush_all();report.invalidate_recordset()
        self.assertEqual(set(report.mapped('valuation_status')),{'missing'})

    def test_current_version_and_company_security(self):
        estimate,price=self.sample();estimate.action_validate_estimate();estimate.action_activate_estimate()
        new=self.env['step.export.estimate'].browse(estimate.action_new_estimate_version()['res_id'])
        new.action_validate_estimate();new.action_activate_estimate();self.env.flush_all()
        rows=self.env['step.producer.estimate.report'].search([('estimate_id','in',(estimate|new).ids),('state','=','current')])
        self.assertEqual(len(rows),2);self.assertEqual(rows.estimate_id,new)
        other=self.env['res.company'].create({'name':'QA T68 other'})
        user=new_test_user(self.env,login='qa-t68-other',groups='base.group_user',company_id=other.id,company_ids=[Command.set(other.ids)])
        self.assertFalse(rows.with_user(user).with_context(allowed_company_ids=other.ids).search([('id','in',rows.ids)]))
        with self.assertRaises(AccessError):
            rows.with_user(user).write({'export_kg':10})

    def test_price_specificity_units_and_currency_match_native_conversion(self):
        estimate,price=self.sample()
        product=estimate.estimate_line_ids.product_id
        price.line_ids.copy({'product_id':product.id,'price':3000,'uom_id':self.env.ref('uom.product_uom_ton').id})
        self.env.flush_all()
        rows=self.env['step.producer.estimate.report'].search([('estimate_id','=',estimate.id)])
        self.assertAlmostEqual(sum(rows.mapped('amount_usd')),300)
        selected=self.env['step.producer.preliq.price'].resolve_price(estimate.company_id,estimate.season_id,estimate.estimate_line_ids.species_id,estimate.estimate_line_ids.variety_id,date(2026,11,2),product=product)
        self.assertEqual(rows.price_line_id,selected)
        currency=self.env['res.currency'].create({'name':'Q68','symbol':'Q68','rounding':0.01})
        usd=self.env.ref('base.USD')
        self.env['res.currency.rate'].create({'currency_id':currency.id,'name':date(2026,11,1),'rate':2,'company_id':estimate.company_id.id})
        self.env['res.currency.rate'].create({'currency_id':usd.id,'name':date(2026,11,1),'rate':1,'company_id':estimate.company_id.id})
        price.currency_id=currency;self.env.flush_all();rows.invalidate_recordset()
        self.assertAlmostEqual(sum(rows.mapped('amount_usd')),150)
        self.assertAlmostEqual(rows[0].price_usd_per_kg,currency._convert(3,usd,estimate.company_id,date(2026,11,2),round=False))
        selected.uom_id=self.env.ref('uom.product_uom_unit');self.env.flush_all();rows.invalidate_recordset()
        self.assertEqual(set(rows.mapped('valuation_status')),{'unit'})

    def test_packed_delivery_does_not_count_process_kilos_or_bins(self):
        estimate,price=self.sample();estimate.estimate_line_ids.delivery_kind='packed';self.env.flush_all()
        rows=self.env['step.producer.estimate.report'].search([('estimate_id','=',estimate.id)])
        self.assertEqual(sum(rows.mapped('process_kg')),0)
        self.assertEqual(sum(rows.mapped('bin_qty')),0)
        self.assertEqual(sum(rows.mapped('export_box_qty')),20)
        self.assertEqual(sum(rows.mapped('export_pallet_qty')),2)
