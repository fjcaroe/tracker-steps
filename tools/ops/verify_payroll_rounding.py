"""Effective source, native payroll form/menu and prospective-only rounding."""
import importlib
import json
from datetime import date
from pathlib import Path
from odoo.tools import config

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name','=',name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent == Path(ROOT)/name
    candidates = env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1)])
    users = candidates.filtered(lambda u: u.has_group('hr_payroll.group_hr_payroll_manager'))
    assert users, 'Existing payroll manager required'
    company = env['res.company'].search([('vat','=','76943293-0')]) if 'CERRO' in env.cr.dbname else env.ref('base.main_company')
    assert len(company)==1
    users = users.filtered(lambda u: company in u.company_ids)
    assert users, 'Existing payroll manager for destination company required'
    user = users[:1]
    scoped = env(user=user,su=False,context=dict(env.context,allowed_company_ids=company.ids))
    visible = scoped['ir.ui.menu']._visible_menu_ids()
    menus = scoped['ir.ui.menu'].search([('id','in',list(visible)),('action','!=',False)])
    assert menus.filtered(lambda m: m.action._name=='ir.actions.act_window' and m.action.res_model=='hr.payslip')
    previous = config['test_enable'];config['test_enable']=True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable']=previous
    payslips = scoped['hr.payslip']
    slip = payslips.search([],limit=1)
    Form(slip or payslips)
    structure = scoped.ref('l10n_cl_simpledigital_payroll.structure_chile')
    company = scoped.company
    assert company.currency_id.name == 'CLP'
    draft = payslips.new({'company_id':company.id,'struct_id':structure.id,
        'date_from':date(2026,10,1),'date_to':date(2026,10,31),'state':'draft'})
    rule = scoped['hr.salary.rule']
    assert draft._get_payslip_line_total(10.6,1,100,rule)==11
    draft.date_from=date(2026,9,1)
    assert draft._get_payslip_line_total(10.6,1,100,rule)==10.6
    draft.date_from=date(2026,10,1);draft.state='done'
    assert draft._get_payslip_line_total(10.6,1,100,rule)==10.6
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':113,'versions':EXPECTED,
        'existing_profile':user.id,'company_id':company.id,'native_payroll_menu_and_form':True,
        'round_before_categories':True,'effective_from':'2026-10-01',
        'historical_states_unchanged':True,'writes':False}))
finally:
    env.cr.rollback()
