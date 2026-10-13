from lxml import etree
from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user


class ProvisionCase(TransactionCase):
    def sample(self):
        clp=self.env.ref('base.CLP');usd=self.env.ref('base.USD')
        company=self.env['res.company'].create({'name':'QA T79 company','currency_id':clp.id,'country_id':self.env.ref('base.cl').id})
        env=self.env(context=dict(self.env.context,allowed_company_ids=company.ids,no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True)).with_company(company)
        debit=env['account.account'].create({'name':'QA T79 expense','code':'QA7901','account_type':'expense','company_ids':[Command.set(company.ids)]})
        credit=env['account.account'].create({'name':'QA T79 provision','code':'QA7902','account_type':'liability_current','company_ids':[Command.set(company.ids)]})
        journal=env['account.journal'].create({'name':'QA T79 general','code':'QA79','type':'general','company_id':company.id,'default_account_id':credit.id})
        usd.active=True
        env['res.currency.rate'].create({'currency_id':usd.id,'company_id':company.id,'name':'2026-11-02','rate':1/900})
        accounts=env['account.analytic.account']
        for label in ('season','species','shipment'):
            plan=env['account.analytic.plan'].create({'name':'QA T79 '+label,'default_applicability':'optional'})
            accounts |= env['account.analytic.account'].create({'name':'QA T79 '+label,'plan_id':plan.id,'company_id':company.id})
        season=env['step.temporada'].create({'name':'QA T79 season','cost_id':accounts[0].id})
        species=env['step.especie'].create({'name':'QA T79 species','type_especie':'frutal','group_especie':'baya','cost_id':accounts[1].id})
        receiver=env['res.partner'].create({'name':'QA T79 receiver','step_export_receiver':True})
        vendor=env['res.partner'].create({'name':'QA T79 vendor','country_id':env.ref('base.cl').id})
        category=env['product.category'].create({'name':'QA T79 category','property_account_expense_categ_id':debit.id})
        product=env['product.product'].create({'name':'QA T79 service','categ_id':category.id,'type':'service'})
        fruit=env['product.product'].create({'name':'QA T79 fruit','is_fruta':True})
        package=env['stock.package.type'].create({'name':'QA T79 pallet'})
        program=env['step.export.sales.program'].create({'name':'QA T79 program','partner_id':receiver.id,'season_id':season.id,'species_id':species.id,
            'product_id':fruit.id,'package_type_id':package.id,'date_start':'2026-11-02','date_end':'2026-11-16','rate_to_usd':1,'currency_id':usd.id})
        shipment=env['step.export.export'].create({'name':'QA T79 shipment','sales_program_id':program.id,'season_id':season.id,'species_id':species.id,
            'receiver_id':receiver.id,'departure_date':'2026-11-03','provision_analytic_account_id':accounts[2].id,'company_id':company.id})
        item=env['step.export.grower.discount'].create({'name':'QA T79 grower item','company_id':company.id})
        document=env['l10n_latam.document.type'].search([('country_id','=',env.ref('base.cl').id)],limit=1)
        if not document:document=env['l10n_latam.document.type'].create({'name':'QA T79 document','code':'QA79','country_id':env.ref('base.cl').id,'internal_type':'invoice'})
        record=env['step.export.shipment.provision'].create({'season_id':season.id,'program_id':program.id,'shipment_id':shipment.id,'company_id':company.id,
            'journal_id':journal.id,'date':'2026-11-02','line_ids':[Command.create({'grower_item_id':item.id,'product_id':product.id,'vendor_id':vendor.id,
                'document_type_id':document.id,'document_number':'QA-79','currency_id':usd.id,'amount_currency':100})]})
        return record

    def test_full_flow_balanced_daily_rate_analytics(self):
        record=self.sample();record.action_validate();record.action_cost()
        self.assertEqual(record.state,'costed');self.assertAlmostEqual(record.amount_clp,90000);self.assertEqual(record.amount_usd,100)
        record.action_account();move=record.move_id
        self.assertEqual(record.state,'posted');self.assertEqual(move.state,'posted')
        self.assertEqual(sum(move.line_ids.mapped('balance')),0)
        self.assertEqual(sum(move.line_ids.mapped('debit')),90000)
        self.assertEqual(sum(move.line_ids.mapped('amount_currency')),0)
        self.assertEqual(move.line_ids.filtered(lambda l:l.debit).analytic_distribution,record.analytic_distribution)
        self.assertEqual(len(move.line_ids.filtered(lambda l:l.debit).analytic_line_ids),3)
        record.action_account();self.assertEqual(record.move_id,move)

    def test_validation_company_and_sources(self):
        record=self.sample()
        other=record.env['step.temporada'].create({'name':'QA wrong season'})
        record.season_id=other
        with self.assertRaises(ValidationError):record.action_validate()
        record.season_id=record.program_id.season_id
        record.line_ids.amount_currency=0
        with self.assertRaises(ValidationError):record.action_validate()

    def test_missing_analytic_or_expense_configuration(self):
        record=self.sample();record.shipment_id.provision_analytic_account_id=False;record.action_validate()
        with self.assertRaises(ValidationError):record.action_cost()
        record.shipment_id.provision_analytic_account_id=record.season_id.cost_id
        with self.assertRaises(ValidationError):record.action_cost()

    def test_freeze_and_forbidden_state_injection(self):
        record=self.sample()
        with self.assertRaises(UserError):record.state='posted'
        with self.assertRaises(UserError):record.line_ids.amount_clp=1
        record.action_validate()
        with self.assertRaises(UserError):record.date='2026-11-03'
        with self.assertRaises(UserError):record.line_ids.amount_currency=200
        record.action_cost();record.action_account()
        with self.assertRaises(UserError):record.move_id.button_draft()
        with self.assertRaises(UserError):record.move_id.button_cancel()
        with self.assertRaises(UserError):record.unlink()

    def test_cost_snapshot_not_revalued_after_rate_change(self):
        record=self.sample();record.action_validate();record.action_cost()
        rate=record.env['res.currency.rate'].search([('company_id','=',record.company_id.id),('currency_id','=',record.usd_currency_id.id)])
        rate.rate=1/1000
        record.action_account()
        self.assertEqual(sum(record.move_id.line_ids.mapped('debit')),90000)

    def test_roles_menu_form_company_isolation(self):
        record=self.sample();env=record.env
        user=new_test_user(env,login='qa-t79-planner',groups='stock.group_stock_manager',company_id=record.company_id.id,company_ids=[Command.set(record.company_id.ids)])
        self.assertIn(env.ref('step_export_shipment_provision.provision_menu').id,env['ir.ui.menu'].with_user(user)._visible_menu_ids())
        arch=etree.fromstring(record.with_user(user).get_view(view_id=env.ref('step_export_shipment_provision.provision_form').id,view_type='form')['arch'].encode())
        self.assertTrue(arch.xpath('.//field[@name="shipment_id"]'))
        record.action_validate();record.action_cost()
        with self.assertRaises(UserError):record.with_user(user).action_account()
        other=env['res.company'].create({'name':'QA T79 other'})
        outsider=new_test_user(env,login='qa-t79-outsider',groups='stock.group_stock_user',company_id=other.id,company_ids=[Command.set(other.ids)])
        self.assertFalse(record.with_user(outsider).with_context(allowed_company_ids=other.ids).search([('id','=',record.id)]))
