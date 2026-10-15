from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class BalanceAnalyticCase(TransactionCase):
    def prepare(self):
        self.company=self.env.company
        self.plan=self.env['account.analytic.plan'].create({'name':'Plan obligatorio QA T88','default_applicability':'mandatory'})
        self.analytic=self.env['account.analytic.account'].create({'name':'Centro QA T88','plan_id':self.plan.id,'company_id':self.company.id})
        self.journal=self.env['account.journal'].create({'name':'Diario QA T88','code':'QT88','type':'general','company_id':self.company.id})

    def account(self, kind, suffix):
        if kind == 'equity_unaffected':
            existing=self.env['account.account'].with_company(self.company).search([('account_type','=',kind),('company_ids','in',self.company.id)],limit=1)
            if existing:
                return existing
        return self.env['account.account'].create({'name':'Cuenta QA T88 '+kind,'code':'QT88'+suffix,
            'account_type':kind,'company_ids':[(6,0,self.company.ids)],
            'reconcile':kind in ('asset_receivable','liability_payable')})

    def move(self, debit, credit, distribution=False):
        return self.env['account.move'].create({'move_type':'entry','journal_id':self.journal.id,'date':'2026-10-15',
            'line_ids':[(0,0,{'name':'Debe QA T88','account_id':debit.id,'debit':100}),
                        (0,0,{'name':'Haber QA T88','account_id':credit.id,'credit':100,'analytic_distribution':distribution})]})

    def distribution(self, account):
        values={}
        for plan in self.env['account.analytic.plan'].get_relevant_plans(company_id=self.company.id,account=account.id,business_domain='general'):
            if plan['applicability']=='mandatory':
                analytic=self.env['account.analytic.account'].create({'name':'Dimension QA T88','plan_id':plan['id'],'company_id':self.company.id})
                values[str(analytic.id)]=100
        return values

    def test_balance_and_equity_can_post_without_analytics(self):
        self.prepare()
        kinds=('asset_receivable','asset_cash','asset_current','asset_non_current','asset_prepayments','asset_fixed',
               'liability_payable','liability_credit_card','liability_current','liability_non_current','equity','equity_unaffected')
        accounts=[self.account(kind,str(i)) for i,kind in enumerate(kinds)]
        for account in accounts:
            self.assertEqual(self.plan._get_applicability(account=account.id,company_id=self.company.id,business_domain='general'),'optional')
        move=self.move(accounts[2],accounts[8])
        move.action_post()
        self.assertEqual(move.state,'posted')
        self.assertFalse(move.line_ids.mapped('analytic_line_ids'))
        self.assertFalse(any(move.line_ids.mapped('analytic_distribution')))

    def test_result_still_requires_complete_distribution(self):
        self.prepare()
        asset=self.account('asset_current','A')
        income=self.account('income','I')
        expense=self.account('expense','E')
        for account in (income,expense):
            self.assertEqual(self.plan._get_applicability(account=account.id,company_id=self.company.id,business_domain='general'),'mandatory')
        move=self.move(asset,income)
        with self.assertRaises(ValidationError),self.cr.savepoint():
            move.action_post()
        values=self.distribution(income)
        with self.assertRaises(ValidationError),self.cr.savepoint():
            move.line_ids.filtered(lambda line:line.credit).analytic_distribution={key:50 for key in values}
            move.action_post()
        move.line_ids.filtered(lambda line:line.credit).analytic_distribution=values
        move.action_post()
        self.assertEqual(move.state,'posted')
        self.assertTrue(move.line_ids.mapped('analytic_line_ids'))

    def test_native_plan_rules_and_company_context_are_preserved(self):
        self.prepare()
        asset=self.account('asset_current','A')
        income=self.account('income','I')
        self.assertEqual(self.plan._get_applicability(account=asset.id,applicability='mandatory'),'mandatory')
        self.plan.default_applicability='unavailable'
        self.assertEqual(self.plan._get_applicability(account=asset.id),'unavailable')
        self.plan.default_applicability='optional'
        self.assertEqual(self.plan._get_applicability(account=income.id),'optional')
        other=self.env['res.company'].create({'name':'Empresa QA T88'})
        self.plan.with_company(other).default_applicability='mandatory'
        self.assertEqual(self.plan.with_company(self.company)._get_applicability(account=income.id,company_id=self.company.id),'optional')
        self.assertEqual(self.plan.with_company(other)._get_applicability(account=income.id,company_id=other.id),'mandatory')
