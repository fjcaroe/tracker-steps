"""T143 installed source and native payroll access without business writes."""
import importlib
import json
from pathlib import Path
from odoo.tools import config

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    company=env['res.company'].search([('vat','=','76943293-0')]) if 'CERRO' in env.cr.dbname else env.ref('base.main_company')
    assert len(company)==1
    users=env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1)])
    users=users.filtered(lambda u: company in u.company_ids and u.has_group('hr_payroll.group_hr_payroll_manager'))
    assert users,'Existing payroll manager required'
    scoped=env(user=users[:1],su=False,context=dict(env.context,allowed_company_ids=company.ids))
    menus=scoped['ir.ui.menu'].search([('id','in',list(scoped['ir.ui.menu']._visible_menu_ids())),('action','!=',False)])
    assert menus.filtered(lambda m:m.action._name=='ir.actions.act_window' and m.action.res_model=='hr.payslip')
    previous=config['test_enable'];config['test_enable']=True
    try:
        from odoo.tests import Form
    finally:config['test_enable']=previous
    slips=scoped['hr.payslip'];Form(slips.search([],limit=1) or slips)
    if env.cr.dbname.startswith('MANAGEMENT_QA_SYS_'):
        from odoo.exceptions import UserError
        from odoo import fields
        plan=json.loads((Path(PROBE_TOOLS).parents[1]/'attendance-replay.json').read_text())
        assert plan, 'Reported case must be located in the fresh SyS copy'
        for case in plan:
            company=env['res.company'].browse(case['company_id'])
            candidates=env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1)])
            candidates=candidates.filtered(lambda u:company in u.company_ids and u.has_group('hr_payroll.group_hr_payroll_manager'))
            assert candidates
            business=env(user=candidates[:1],su=False,context=dict(env.context,allowed_company_ids=company.ids))
            slip=business['hr.payslip'].browse(case['payslip_id'])
            assert slip.state=='done', 'Reported case changed: inspect the fresh human/business state'
            entries=business['hr.work.entry'].browse([row['id'] for row in case['entries'] if row['state']=='validated' and row['start'][:10] in ('2026-10-30','2026-10-31')])
            assert entries
            env.flush_all()
            before={}
            for table in ('hr_payslip','hr_payslip_line','hr_work_entry','hr_contract','account_move','account_move_line'):
                env.cr.execute("SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY id),'')) FROM "+table+' t')
                before[table]=env.cr.fetchone()
            rejected=False
            try:
                with env.cr.savepoint():
                    entries.unlink()
            except UserError:
                rejected=True
            assert rejected and entries.exists()==entries
            env.flush_all()
            for table,expected in before.items():
                env.cr.execute("SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY id),'')) FROM "+table+' t')
                assert env.cr.fetchone()==expected
        print('T143_REPORTED_CONFIRMED_CASE_PROTECTED no_business_changes=True')
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':143,'versions':EXPECTED,'existing_profile':scoped.uid,
        'company_id':scoped.company.id,'native_payroll_menu_and_form':True,'writes':False}))
finally:
    env.cr.rollback()
