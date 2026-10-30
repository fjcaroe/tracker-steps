"""T138 source, native form/menu, and real unpaid-case calculation in clones."""
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
        plan=json.loads((Path(PROBE_TOOLS).parents[1]/'payroll-days-replay.json').read_text())
        company=env['res.company'].browse(plan['company_id']);manager=users.filtered(lambda u:company in u.company_ids)[:1]
        assert manager
        business=env(user=manager,su=False,context=dict(env.context,allowed_company_ids=company.ids))
        def snapshot(sql,args=None):
            env.cr.execute(sql,args or []);return env.cr.fetchone()
        env.flush_all()
        paid=snapshot("SELECT md5(coalesce(string_agg(to_jsonb(p)::text,'' ORDER BY p.id),'')) FROM hr_payslip p WHERE p.state IN ('done','paid')")
        paid_lines=snapshot("SELECT md5(coalesce(string_agg(to_jsonb(l)::text,'' ORDER BY l.id),'')) FROM hr_payslip_line l JOIN hr_payslip p ON p.id=l.slip_id WHERE p.state IN ('done','paid')")
        unchanged={}
        for table in ('hr_work_entry','hr_contract','account_move','account_move_line'):
            unchanged[table]=snapshot("SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY id),'')) FROM "+table+' t')
        env.cr.execute('SELECT id,to_jsonb(t) FROM hr_leave t');leave_before=dict(env.cr.fetchall())
        staff=business['hr.payslip'].browse([case['payslip_id'] for case in plan['cases']]).employee_id
        eligible=business['hr.leave'].search([('employee_id','in',staff.ids),('state','!=','refuse'),
            ('payslip_state','!=','blocked'),('date_to','<=','2026-10-31 23:59:59.999999')]).ids
        for case in plan['cases']:
            slip=business['hr.payslip'].browse(case['payslip_id']).exists()
            assert slip and slip.company_id==company and slip.state in ('draft','verify') and not slip.move_id
            assert str(slip.date_from)=='2026-10-01' and str(slip.date_to)=='2026-10-31'
            original_inputs=slip.input_line_ids.read(['input_type_id','amount','name'])
            source_absence=slip.worked_days_line_ids.filtered(lambda l:l.work_entry_type_id.code in ('FALT','LEAVECL130'))
            original_absence=source_absence.read(['work_entry_type_id','number_of_days','number_of_hours','amount'])
            slip.compute_sheet();env.flush_all()
            attendance=slip.worked_days_line_ids.filtered(lambda l:l.work_entry_type_id.code=='WORK100')
            absence=slip.worked_days_line_ids.filtered(lambda l:l.work_entry_type_id.code in ('FALT','LEAVECL130'))
            assert len(attendance)==1 and sum(absence.mapped('number_of_days'))==case['absent_days']
            assert attendance.number_of_days==30-case['absent_days']
            assert attendance.number_of_hours==8*attendance.number_of_days
            expected=slip.contract_id.wage/30*attendance.number_of_days
            assert attendance.amount==slip.company_id.currency_id.round(expected)
            base=slip.line_ids.filtered(lambda l:l.code=='BASIC')
            assert len(base)==1 and base.total==slip.company_id.currency_id.round(expected)
            assert slip.input_line_ids.read(['input_type_id','amount','name'])==original_inputs
            assert source_absence.read(['work_entry_type_id','number_of_days','number_of_hours','amount'])==original_absence
        for table,value in unchanged.items():
            assert snapshot("SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY id),'')) FROM "+table+' t')==value,table
        env.cr.execute('SELECT id,to_jsonb(t) FROM hr_leave t');leave_after=dict(env.cr.fetchall())
        assert leave_before.keys()==leave_after.keys()
        for ident,before in leave_before.items():
            after=leave_after[ident]
            if ident in eligible:
                assert after['payslip_state']=='done'
                excluded={'payslip_state','write_uid','write_date'}
                assert {k:v for k,v in before.items() if k not in excluded}=={k:v for k,v in after.items() if k not in excluded}
            else:assert before==after
        assert snapshot("SELECT md5(coalesce(string_agg(to_jsonb(p)::text,'' ORDER BY p.id),'')) FROM hr_payslip p WHERE p.state IN ('done','paid')")==paid
        assert snapshot("SELECT md5(coalesce(string_agg(to_jsonb(l)::text,'' ORDER BY l.id),'')) FROM hr_payslip_line l JOIN hr_payslip p ON p.id=l.slip_id WHERE p.state IN ('done','paid')")==paid_lines
        env.cr.rollback()
        env.cr.execute('SELECT id,to_jsonb(t) FROM hr_leave t');assert dict(env.cr.fetchall())==leave_before
        print('T138_NATIVE_CASES_OK one_absence=29 two_absences=28 paid_history_unchanged=True rollback_required=True')
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':138,'versions':EXPECTED,'existing_profile':scoped.uid,
        'company_id':scoped.company.id,'native_payroll_menu_and_form':True,'writes':False}))
finally:
    env.cr.rollback()
