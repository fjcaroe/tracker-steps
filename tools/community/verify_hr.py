"""Real operational HR forms/menu/dashboard as a non-superuser; rollback only."""
try:
    operator=user
    if MODE=='community':
        operator=env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private Community HR verifier','login':'private-community-hr-verifier',
            'company_id':company.id,'company_ids':[(6,0,company.ids)],
            'groups_id':[(6,0,[env.ref(g).id for g in ('base.group_user','hr.group_hr_user',
                'hr_contract.group_hr_contract_manager','step_mobilization.group_mobilization_manager',
                'sales_team.group_sale_manager','product.group_product_pricelist')])],
        })
    scoped_hr=api.Environment(env.cr,operator.id,dict(env.context,allowed_company_ids=company.ids),su=False)
    assert not scoped_hr.su
    for model in ('step.tracker','step.tracker.machine','step.tracker.driver','step.tracker.field',
                  'step.tracker.session','step.tracker.work_order','step.history'):
        scoped_hr[model].check_access('read')
        assert scoped_hr[model].get_view(view_type='form')['arch']
    visible=scoped_hr['ir.ui.menu']._visible_menu_ids()
    assert scoped_hr.ref('step_hr.menu_step_hr_root').id in visible
    assert scoped_hr.ref('step_hr.menu_step_activities_dashboard').id in visible
    dashboard=scoped_hr['hr.salary.custom'].get_activities_dashboard_data(0)
    assert dashboard['mobilization_installed'] and 'kpis' in dashboard
    assert scoped_hr['res.partner']._fields['duplicate_bank_partner_ids'].type==('many2many' if MODE=='community' else 'boolean')
    if MODE=='community':
        assert 'hr.payslip' not in env.registry.models
    else:
        for name in ('view_salary_payroll_bridge','view_tarja_payroll_bridge','hr_payslip_step_view_tree','step_view_res_partner_map'):
            assert env.ref('step_hr.'+name)==env.ref('step_hr_payroll_bridge.'+name)
        assert env['hr.payslip']._fields['net_liquido'].store
    print('HR_NATIVE_OK '+json.dumps({'uid':operator.id,'company':company.id,'su':False,
        'original_app':True,'tracker_forms':True,'dashboard':True,'real_payroll_bridge':MODE!='community',
        'external_tracker_api_invoked':False,'paid_payroll_invoked':False}))
finally:
    env.cr.rollback()
