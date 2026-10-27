"""Harvest/planning/records native forms, original packaging and real payroll bridge."""
from odoo.addons.step_agriculture_format_core.ownership import RECORDS as FORMAT_RECORDS
from odoo.addons.step_labor_reports.ownership import RECORDS as REPORT_RECORDS
try:
    operator=user
    if MODE=='community':
        operator=env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private Community harvest verifier','login':'private-community-harvest-verifier',
            'company_id':company.id,'company_ids':[(6,0,company.ids)],
            'groups_id':[(6,0,[env.ref(g).id for g in ('base.group_user','hr.group_hr_user',
                'sales_team.group_sale_manager','product.group_product_pricelist',
                'step_management_costs.group_management_manager')])],
        })
    scoped_harvest=api.Environment(env.cr,operator.id,dict(env.context,allowed_company_ids=company.ids),su=False)
    assert not scoped_harvest.su
    for namespace,records,legacy in [('step_agriculture_format_core',FORMAT_RECORDS,'step_export'),
                                      ('step_labor_reports',REPORT_RECORDS,'step_hr')]:
        for name in records:
            assert env.ref(namespace+'.'+name)==env.ref(legacy+'.'+name),name
    for model,ref in [('step.cosecha.registry','step_cosecha.view_step_cosecha_registry_form'),
                       ('product.packaging','step_export.view_step_export_packaging_form'),
                       ('report.step.hrs.wizard','step_labor_reports.report_step_hrs_wizard_form'),
                       ('report.by.process.wizard','step_labor_reports.report_step_by_process_form')]:
        scoped_harvest[model].get_view(scoped_harvest.ref(ref).id,'form')
    visible=scoped_harvest['ir.ui.menu']._visible_menu_ids()
    assert scoped_harvest.ref('step_cosecha_planning.menu_packaging').id in visible
    product=scoped_harvest['product.product'].create({'name':'Private harvest package verification','grupo_labor':'pack'})
    with Form(scoped_harvest['product.packaging'],view='step_export.view_step_export_packaging_form') as form:
        form.name='Private harvest format';form.product_id=product;form.qty=12
        form.step_export_kg_per_box=7.125;form.step_packaging_group='harvest'
    package=form.record
    assert package.product_id==product and package.step_export_kg_per_box==7.125
    harvest=scoped_harvest['step.cosecha.registry'].create({'name':'Private harvest verification',
        'company_id':company.id,'product_uom_id':env.ref('uom.product_uom_kgm').id})
    harvest.write({'type_tarea':'contratista','tarja_kg':400,'tarja_cajas':20})
    harvest.action_apro();harvest.action_in();assert harvest.state=='in'
    report=scoped_harvest['report.step.hrs.wizard'].create({'date_from':'2099-01-01','date_to':'2099-01-02'})
    report.generate_report();assert report.file
    from odoo.addons.step_agriculture_records.schema import MODELS as HARVEST_RECORD_MODELS
    for model in HARVEST_RECORD_MODELS.values():
        scoped_harvest[model].get_view(view_type='form')
    if MODE=='community':
        assert 'hr.input.step.wizard' not in env.registry.models
        assert not env['ir.module.module'].search_count([('name','=','step_labor_payroll_wizards'),('state','=','installed')])
    else:
        for name,comodel in [('payslip_run_id','hr.payslip.run'),('struct_id','hr.payroll.structure'),('input_type_id','hr.payslip.input.type')]:
            assert env['hr.input.step.wizard']._fields[name].comodel_name==comodel
            assert comodel in env.registry.models
        assert env['ir.model.relation'].search([('name','=','step_hr_payslip_rel')]).module.name=='step_labor_payroll_wizards'
        assert env.ref('step_hr.step_payslip_wizard_form')==env.ref('step_labor_payroll_wizards.step_payslip_wizard_form')
    print('HARVEST_NATIVE_OK '+json.dumps({'uid':operator.id,'company':company.id,'su':False,
        'harvest_workflow':True,'packaging_native':True,'record_forms':len(HARVEST_RECORD_MODELS),
        'report_download':True,'real_payroll_bridge':MODE!='community','paid_payroll_invoked':False}))
finally:
    env.cr.rollback()
