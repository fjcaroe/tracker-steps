"""Labor operations forms and costs with an existing profile; rollback only."""
from odoo.addons.step_labor_operations_core.ownership import RECORDS
from odoo import fields

try:
    for name in RECORDS:
        assert env.ref('step_hr.'+name) == env.ref('step_labor_operations_core.'+name),name
    operator=user
    if MODE=='community':
        # Settings rights do not imply Mobilization roles. Use a disposable
        # business profile, never grant groups to an existing user.
        operator=env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private Community labor verifier','login':'private-community-labor-verifier',
            'company_id':company.id,'company_ids':[(6,0,company.ids)],
            'groups_id':[(6,0,[env.ref(g).id for g in ('base.group_user','hr.group_hr_user',
                'hr_contract.group_hr_contract_manager','step_mobilization.group_mobilization_manager',
                'sales_team.group_sale_manager','product.group_product_pricelist')])],
        })
    scoped_labor=api.Environment(env.cr,operator.id,dict(env.context,allowed_company_ids=company.ids),su=False)
    assert not scoped_labor.su
    visible=scoped_labor['ir.ui.menu']._visible_menu_ids()
    root=scoped_labor.ref('step_labor_operations_core.menu_labor_operations')
    if not scoped_labor.ref('step_hr.menu_step_hr_root',raise_if_not_found=False):
        assert root.active and root.id in visible
        assert scoped_labor.ref('step_labor_operations_core.menu_task_own').id in visible
    else:
        assert not root.active
        legacy_menu=scoped_labor.ref('step_hr.menu_step_tarja')
        if legacy_menu.active:
            assert legacy_menu.id in visible
    for model,view in [('hr.salary.custom','view_hr_salary_custom_form'),
                       ('step.tarja','view_step_tarja_form'),('hr.contract','step_view_hr_contract_form')]:
        scoped_labor[model].get_view(scoped_labor.ref('step_hr.'+view).id,'form')
    if MODE=='community':
        assert 'payslip_run_id' not in scoped_labor['hr.salary.custom']._fields
        assert not hasattr(scoped_labor['step.tarja'],'envio_nomina')
    employee=scoped_labor['hr.employee'].create({'name':'Private labor verification','company_id':company.id})
    contract=scoped_labor['hr.contract'].create({'name':'Private labor contract verification',
        'employee_id':employee.id,'company_id':company.id,
        'date_start':fields.Date.context_today(scoped_labor['hr.contract']).replace(day=1),'wage':800000,
        'resource_calendar_id':company.resource_calendar_id.id})
    # Omit explicit type during these reversible native API checks so the
    # legacy create override doesn't consume the customer's SQL sequence.
    # Automatic numbering is exercised separately with isolated company fixtures.
    crew=scoped_labor['hr.salary.custom'].create({'name':'Private crew verification','company_id':company.id})
    crew.write({'group_type':'propio'})
    tarja=scoped_labor['step.tarja'].create({'name':'Private tarja verification','salary_id':crew.id,
        'company_id':company.id,'date':'2026-10-27','tarja_line':[(0,0,{'employee_id':employee.id,
            'contract_id':contract.id,'hrs':1})]})
    assert tarja.tarja_line.hrs_total==1
    tarja.action_auto();tarja.action_costeo();assert tarja.state=='costo'
    scoped_labor['step.movi.registry'].get_view(
        scoped_labor.ref('step_mobilization.view_step_movi_registry_form').id,'form')
    scoped_labor['step.movi.registry'].search_count([])
    print('LABOR_NATIVE_OK '+json.dumps({'uid':operator.id,'company_id':company.id,'su':False,
        'crew_create':True,'tarja_costing':True,'contract_form':True,'mobilization_form':True,
        'legacy_xmlids':len(RECORDS),'menus':True,'numbering':'isolated fixtures only'}))
finally:
    env.cr.rollback()
