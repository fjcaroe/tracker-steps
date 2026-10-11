from datetime import date
from odoo import Command
from odoo.tests.common import TransactionCase, new_test_user
from odoo.exceptions import AccessError, UserError


class ContractReportCase(TransactionCase):
    def sample(self, unit=False, quantity=100, price=2, currency=False):
        env=self.env
        partner=env['res.partner'].create({'name':'QA T69 producer','is_productor':True})
        species=env['step.especie'].create({'name':'QA T69 fruit','type_especie':'frutal','group_especie':'fruta_h'})
        group=env['step.grupo.variedad'].create({'name':'QA T69 group','especie_id':species.id})
        variety=env['step.variedad'].create({'name':'QA T69 variety','cod_variedad':'QA-T69','especie_id':species.id,'grupo_variedad_id':group.id})
        season=env['step.temporada'].create({'name':'QA T69 season'})
        kg=env.ref('uom.product_uom_kgm')
        product=env['product.product'].create({'name':'QA T69 fruit','purchase_ok':True,'type':'consu',
            'step_export_species_id':species.id,'step_export_enabled':True,'uom_id':kg.id,'uom_po_id':kg.id})
        contract=env['step.producer.purchase.contract'].create({'partner_id':partner.id,'season_id':season.id,
            'currency_id':(currency or env.ref('base.USD')).id,'date_start':date(2026,9,1),'date_end':date(2027,1,31)})
        line=env['step.producer.purchase.contract.product'].create({'contract_id':contract.id,'product_id':product.id,
            'species_id':species.id,'variety_id':variety.id,'quantity':quantity,'price_unit':price,'uom_id':(unit or kg).id})
        env['step.producer.purchase.contract.installment'].create([
            {'contract_id':contract.id,'product_line_id':line.id,'quantity':quantity*.4,'date_due':date(2026,11,30)},
            {'contract_id':contract.id,'product_line_id':line.id,'quantity':quantity*.6,'date_due':date(2026,12,18)}])
        env.flush_all()
        return contract

    def rows(self, contract, active=True):
        self.env.flush_all()
        return self.env['step.producer.contract.report'].with_context(active_test=False).search([('contract_id','=',contract.id),('active','=',active)])

    def test_schedule_is_reported_once_and_updates_live(self):
        c=self.sample();rows=self.rows(c)
        self.assertEqual(len(rows),2);self.assertEqual(sum(rows.mapped('quantity_kg')),100)
        self.assertEqual(sum(rows.mapped('amount_usd')),200)
        self.assertEqual(rows.season_id,c.season_id)
        self.assertEqual(rows.species_id,c.product_line_ids.species_id)
        self.assertEqual(rows.variety_id,c.product_line_ids.variety_id)
        c.product_line_ids.price_unit=3;self.env.flush_all();rows.invalidate_recordset()
        self.assertEqual(sum(rows.mapped('amount_usd')),300)
        self.assertEqual({r.date_due for r in rows},{date(2026,11,30),date(2026,12,18)})

    def test_revision_keeps_accounted_quota_without_duplicate_pending_payments(self):
        c=self.sample();c.action_confirm()
        first=c.installment_ids.sorted('date_due')[0];first.state='accounted'
        revision=c.browse(c.action_revise()['res_id'])
        self.assertEqual(revision.season_id,c.season_id)
        revision.action_confirm();self.env.flush_all()
        rows=self.env['step.producer.contract.report'].search([('contract_id','in',(c|revision).ids)])
        self.assertEqual(len(rows),2)
        self.assertEqual(sum(rows.mapped('quantity_kg')),100)
        self.assertEqual(sum(rows.mapped('amount_usd')),200)
        self.assertEqual(len(self.rows(c,active=False)),1)

    def test_mass_units_are_converted_and_other_units_flagged(self):
        c=self.sample(unit=self.env.ref('uom.product_uom_ton'),quantity=.1,price=2000)
        self.assertAlmostEqual(sum(self.rows(c).mapped('quantity_kg')),100)
        self.assertAlmostEqual(sum(self.rows(c).mapped('amount_usd')),200)
        other=self.sample(unit=self.env.ref('uom.product_uom_unit'))
        rows=self.rows(other)
        self.assertEqual(sum(rows.mapped('quantity_kg')),0)
        self.assertEqual(sum(rows.mapped('unconverted_kg_qty')),2)
        self.assertEqual(sum(rows.mapped('amount_usd')),200)

    def test_usd_conversion_uses_due_date_and_flags_missing_rates(self):
        currency=self.env['res.currency'].create({'name':'Q69','symbol':'Q69','rounding':.01})
        c=self.sample(currency=currency);rows=self.rows(c)
        self.assertEqual(set(rows.mapped('valuation_status')),{'rate'})
        self.assertEqual(sum(rows.mapped('unconverted_qty')),2)
        usd=self.env.ref('base.USD')
        for curr,rate in [(currency,2),(usd,1)]:
            self.env['res.currency.rate'].create({'currency_id':curr.id,'name':date(2026,11,1),'rate':rate,'company_id':c.company_id.id})
        self.env['res.currency.rate'].create({'currency_id':currency.id,'name':date(2026,12,1),'rate':4,'company_id':c.company_id.id})
        self.env.flush_all();rows.invalidate_recordset()
        self.assertEqual(sum(rows.mapped('amount_usd')),70)
        for row in rows:
            self.assertAlmostEqual(row.amount_usd,currency._convert(row.amount,usd,c.company_id,row.date_due,round=False))

    def test_read_only_company_rule_and_catalog_scope(self):
        c=self.sample();rows=self.rows(c)
        user=new_test_user(self.env(context=dict(self.env.context,no_reset_password=True)),login='qa-t69-reader',groups='base.group_user',company_id=c.company_id.id,company_ids=[Command.set(c.company_id.ids)])
        with self.assertRaises(AccessError):rows.with_user(user).write({'quantity_kg':999})
        other=self.env['res.company'].create({'name':'QA T69 other'})
        outsider=new_test_user(self.env(context=dict(self.env.context,no_reset_password=True)),login='qa-t69-outsider',groups='base.group_user',company_id=other.id,company_ids=[Command.set(other.ids)])
        self.assertFalse(rows.with_user(outsider).with_context(allowed_company_ids=other.ids).search([('id','in',rows.ids)]))
        season=self.env['step.temporada'].create({'name':'QA T69 restricted season','company_ids':[Command.set(other.ids)]})
        with self.assertRaises(UserError), self.env.cr.savepoint():c.season_id=season

    def test_historical_classification_and_sealed_season(self):
        c=self.sample();c.season_id=False;c.action_confirm()
        season=self.env['step.temporada'].create({'name':'QA T69 explicit classification'})
        c.season_id=season
        with self.assertRaises(UserError):c.season_id=False
        new=c.browse(c.action_revise()['res_id'])
        self.assertEqual(new.season_id,season)
        new.season_id=False
