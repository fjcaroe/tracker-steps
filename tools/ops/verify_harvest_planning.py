"""T100 effective forms/menus/master reuse probe; all fixture changes roll back."""
import importlib,json
from pathlib import Path
try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    menu=env.ref('step_cosecha_planning.menu_harvest_plan')
    original=env.ref('step_management_costs.menu_harvest_plan')
    assert menu.active and original.active and menu.action==original.action
    assert menu.parent_id==env.ref('step_cosecha.menu_step_cosecha_main_cosecha_plan')
    assert menu.action.res_model=='step.management.harvest.plan'
    for ref,model in [('menu_package_type','stock.package.type'),('menu_packaging','product.packaging')]:
        master=env.ref('step_cosecha_planning.'+ref)
        assert master.active and master.parent_id==env.ref('step_cosecha.step_maestros_cosecha')
        assert master.action.res_model==model
    packaging=env['product.packaging']
    assert packaging._fields['step_packaging_group'].selection==[('export','Exportación'),('national','Nacional'),('harvest','Cosecha')]
    field=env['ir.model.fields'].search([('model','=','product.packaging'),('name','=','step_packaging_group')])
    assert field.state=='base' and not field.required
    for ref,kind in [('product.product_packaging_form_view','form'),('product.product_packaging_tree_view','list'),('step_export.view_step_export_packaging_form','form'),('step_export.view_step_export_packaging_list','list'),('product.product_packaging_search_view','search')]:
        assert 'step_packaging_group' in packaging.get_view(view_id=env.ref(ref).id,view_type=kind)['arch']
    packaging._read_group([],['step_packaging_group'],['__count'])
    for ref,kind in [('step_management_costs.view_harvest_plan_form','form'),('step_management_costs.view_harvest_plan_list','list')]:
        assert env[menu.action.res_model].get_view(view_id=env.ref(ref).id,view_type=kind)['arch']
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        users=env['res.users'].with_context(no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True)
        def profile(login,groups):
            return users.create({'name':login,'login':login,'company_id':env.company.id,'company_ids':[(6,0,env.company.ids)],'groups_id':[(6,0,[env.ref(g).id for g in groups])]})
        reader=profile('qa_t100_reader',['base.group_user','step_management_costs.group_management_readonly'])
        operator=profile('qa_t100_operator',['base.group_user','step_management_costs.group_management_user'])
        basic=profile('qa_t100_basic',['base.group_user'])
        for user in (reader,operator):
            visible=env['ir.ui.menu'].with_user(user)._visible_menu_ids()
            assert menu.id in visible and original.id in visible
            env[menu.action.res_model].with_user(user).get_view(view_id=env.ref('step_management_costs.view_harvest_plan_form').id,view_type='form')
        assert not env[menu.action.res_model].with_user(reader).has_access('write')
        assert env[menu.action.res_model].with_user(operator).has_access('create')
        assert menu.id not in env['ir.ui.menu'].with_user(basic)._visible_menu_ids()
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':100,'versions':EXPECTED,'shared_plan_action':True,'native_masters':True,'forms':True,'groups':3,'permissions_preserved':True}))
finally:
    env.cr.rollback()
