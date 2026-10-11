from datetime import date
from odoo import Command
from odoo.tests.common import TransactionCase, new_test_user
from odoo.exceptions import AccessError

class EstimateReportCase(TransactionCase):
    def sample(self):
        env=self.env
        producer=env['res.partner'].create({'name':'QA T68 producer','is_productor':True})
        packing=env['res.partner'].create({'name':'QA T68 packing','step_export_packing':True})
        fundo=env['step.fundo'].create({'name':'QA T68 farm','partner_id':producer.id})
        season=env['step.temporada'].create({'name':'QA T68 season'})
        species=env['step.especie'].create({'name':'QA T68 fruit','type_especie':'frutal','group_especie':'seco'})
        variety=env['step.variedad'].create({'name':'QA T68 variety','especie_id':species.id})
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
