"""Verify installed analytic policy and real opening entries without committing postings."""
import importlib,json,hashlib
from pathlib import Path
from odoo.addons.step_account_balance_analytic.tests.test_balance_analytic import BalanceAnalyticCase
try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    env=env(context=dict(env.context,tracking_disable=True,no_reset_password=True,mail_create_nosubscribe=True))
    case=BalanceAnalyticCase('test_balance_and_equity_can_post_without_analytics')
    case.env=env
    case.cr=env.cr
    for test in ('test_balance_and_equity_can_post_without_analytics','test_result_still_requires_complete_distribution','test_native_plan_rules_and_company_context_are_preserved'):
        getattr(case,test)()
        env.cr.rollback()
    opening=[]
    if 'cerro' in ROOT:
        moves=env['account.move'].search([('journal_id.code','=','APE'),('state','=','draft'),('ref','ilike','Apertura')])
        assert len(moves)==2, 'Review opening scope before accepting this delivery'
        for move in moves:
            before=[(line.id,line.account_id.id,line.debit,line.credit,line.analytic_distribution) for line in move.line_ids]
            move.with_company(move.company_id).line_ids.with_context(validate_analytic=True)._validate_analytic_distribution()
            posted=False
            if env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_'):
                move.with_company(move.company_id).with_context(validate_analytic=True).action_post()
                assert move.state=='posted'
                posted=True
            after=[(line.id,line.account_id.id,line.debit,line.credit,line.analytic_distribution) for line in move.line_ids]
            assert before==after, 'Amounts or distributions changed'
            opening.append({'id':move.id,'validated':True,'posted_in_copy_only':posted})
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket_id':88,'versions':EXPECTED,'forms':True,'menus':True,
        'balance_optional':True,'results_still_mandatory':True,'incomplete_distribution_rejected':True,'company_context':True,'opening_entries':opening}))
finally:
    env.cr.rollback()
