"""Native greenhouse example and rollback-only manufacturing proof (Odoo shell)."""
from odoo import Command
from odoo.tools import config

NAMESPACE='steps_ecoplantas_greenhouse'
GROUPS=('mrp.group_mrp_manager','mrp.group_mrp_routings','quality.group_quality_manager',
        'maintenance.group_equipment_manager','project.group_project_manager','stock.group_production_lot')
MENUS=('mrp.menu_mrp_root','quality_control.menu_quality_root','maintenance.menu_maintenance_title',
       'project.menu_main_pm','stock.menu_stock_root')


def scenario(env, user_id, *, create=False, exercise=False):
    assert env.cr.dbname=='ECOPLANTAS' or env.cr.dbname.startswith('ECOPLANTAS_GH_QA_')
    assert not exercise or env.cr.dbname.startswith('ECOPLANTAS_GH_QA_')
    company=env.ref('base.main_company')
    assert company.name=='ECOPLANTAS' and company.chart_template=='cl'
    user=env['res.users'].browse(user_id).exists()
    assert user.active and not user.share and user.company_ids==company
    env=env(context=dict(env.context,allowed_company_ids=company.ids,tracking_disable=True,
        mail_notrack=True,mail_create_nosubscribe=True,mail_notify_force_send=False))
    if create:
        user.with_env(env).write({'groups_id':[Command.link(env.ref(group).id) for group in GROUPS]})

    def record(key, model, values):
        found=env.ref(NAMESPACE+'.'+key,raise_if_not_found=False)
        if found:
            assert found._name==model and ('company_id' not in found._fields or found.company_id in (company,env['res.company']))
            return found
        assert create,'Missing demo record '+key
        found=env[model].create(values)
        env['ir.model.data'].create({'module':NAMESPACE,'name':key,'model':model,'res_id':found.id,'noupdate':True})
        return found

    warehouse=env['stock.warehouse'].search([('company_id','=',company.id)],limit=1)
    unit=env.ref('uom.product_uom_unit');litre=env.ref('uom.product_uom_litre')
    assert warehouse and warehouse.manu_type_id
    def location(key,name):
        return record(key,'stock.location',{'name':name+' [DEMO]','usage':'internal',
            'location_id':warehouse.lot_stock_id.id,'company_id':company.id})
    inputs=location('inputs','Insumos de invernadero')
    ready=location('ready','Plantines listos')
    def product(key,name,code,uom,tracking):
        return record(key,'product.product',{'name':name+' [DEMO]','default_code':code,
            'company_id':company.id,'type':'consu','is_storable':True,'tracking':tracking,
            'uom_id':uom.id,'uom_po_id':uom.id})
    seed=product('seed','Semilla de tomate','DEMO-ECO-SEM',unit,'lot')
    substrate=product('substrate','Sustrato de germinación','DEMO-ECO-SUS',litre,'none')
    plant=product('plant','Plantín de tomate','DEMO-ECO-PLA',unit,'lot')
    first=record('sowing','mrp.workcenter',{'name':'Área de siembra [DEMO]','company_id':company.id})
    last=record('transplant','mrp.workcenter',{'name':'Área de trasplante [DEMO]','company_id':company.id})
    bom=record('bom','mrp.bom',{'product_tmpl_id':plant.product_tmpl_id.id,'product_id':plant.id,
        'product_qty':100,'product_uom_id':unit.id,'company_id':company.id,
        'bom_line_ids':[Command.create({'product_id':seed.id,'product_qty':100,'product_uom_id':unit.id}),
                        Command.create({'product_id':substrate.id,'product_qty':25,'product_uom_id':litre.id})],
        'operation_ids':[Command.create({'name':'Siembra y preparación de bandejas','workcenter_id':first.id,'sequence':10}),
                         Command.create({'name':'Trasplante y selección','workcenter_id':last.id,'sequence':20})]})
    point=record('inspection','quality.point',{'title':'Revisión visual del lote de plantines [DEMO]',
        'company_id':company.id,'product_ids':[Command.set(plant.ids)],
        'picking_type_ids':[Command.set(warehouse.manu_type_id.ids)],
        'test_type_id':env.ref('quality_control.test_type_passfail').id,
        'note':'<p>Revise la identificación del lote, la uniformidad y el estado de los plantines.</p>'})
    project=record('project','project.project',{'name':'Labores del invernadero [DEMO]',
        'company_id':company.id,'privacy_visibility':'employees'})
    stage=record('pending','project.task.type',{'name':'Por hacer','project_ids':[Command.set(project.ids)]})
    tasks=env['project.task']
    for key,title in [('irrigation','Registrar riego y condición de bandejas'),('health','Revisar sanidad y uniformidad'),
                      ('move','Trasplantar plantines'),('dispatch','Preparar lote para despacho')]:
        tasks|=record('task_'+key,'project.task',{'name':title+' [DEMO]','project_id':project.id,'stage_id':stage.id})
    equipment=record('pump','maintenance.equipment',{'name':'Bomba de riego [DEMO]',
        'company_id':company.id,'workcenter_id':first.id})
    maintenance=record('pump_check','maintenance.request',{'name':'Revisar bomba y goteros [DEMO]',
        'company_id':company.id,'equipment_id':equipment.id,'maintenance_type':'preventive'})
    supplier=warehouse.in_type_id.default_location_src_id
    receipt=record('receipt','stock.picking',{'picking_type_id':warehouse.in_type_id.id,
        'origin':'[DEMO] Semillas y sustrato','company_id':company.id,
        'location_id':supplier.id,'location_dest_id':inputs.id,
        'move_ids':[Command.create({'name':item.display_name,'product_id':item.id,'product_uom_qty':qty,
            'product_uom':item.uom_id.id,'location_id':supplier.id,'location_dest_id':inputs.id,
            'company_id':company.id}) for item,qty in ((seed,100),(substrate,25))]})
    mo=record('batch','mrp.production',{'origin':'[DEMO] Lote de 100 plantines','company_id':company.id,
        'product_id':plant.id,'product_qty':100,'product_uom_id':unit.id,'bom_id':bom.id,
        'picking_type_id':warehouse.manu_type_id.id,'location_src_id':inputs.id,'location_dest_id':ready.id})

    business=env(user=user,su=False,context=dict(env.context,allowed_company_ids=company.ids))
    old=config['test_enable'];config['test_enable']=True
    try:from odoo.tests import Form
    finally:config['test_enable']=old
    assert set(business.ref(menu).id for menu in MENUS)<=business['ir.ui.menu']._visible_menu_ids()
    for item in (mo,receipt,point,project,maintenance):Form(item.with_env(business))
    assert len(tasks)==4 and mo.state=='draft' and receipt.state=='draft'
    proof={'menus_and_forms':True,'draft_batch':mo.id,'draft_receipt':receipt.id,
        'project':project.id,'maintenance':maintenance.id,'quality_point':point.id,'tasks':len(tasks),
        'native_lot_traceability':plant.tracking=='lot' and seed.tracking=='lot','copy_flow':exercise}
    if exercise:
        receipt=receipt.with_env(business);mo=mo.with_env(business)
        lots=business['stock.lot'];qty=lambda product,location:business['stock.quant']._get_available_quantity(product,location)
        seed_lot=lots.create({'name':'SEMILLA-DEMO-QA','product_id':seed.id,'company_id':company.id})
        receipt.action_confirm()
        for move in receipt.move_ids:
            move.quantity=move.product_uom_qty
            if move.product_id==seed:move.move_line_ids.lot_id=seed_lot
            move.picked=True
        receipt.with_context(skip_backorder=True).button_validate()
        assert receipt.state=='done' and qty(seed,inputs)==100 and qty(substrate,inputs)==25
        mo.action_confirm();mo.action_assign()
        assert len(mo.workorder_ids)==2
        checks=business['quality.check'].search([('production_id','=',mo.id),('point_id','=',point.id)])
        assert checks and all(check.quality_state=='none' for check in checks)
        checks.do_pass()
        lot=lots.create({'name':'PLANTINES-DEMO-QA','product_id':plant.id,'company_id':company.id})
        mo.lot_producing_id=lot;mo.qty_producing=100;mo._set_qty_producing()
        for workorder in mo.workorder_ids:workorder.button_finish()
        mo.with_context(skip_backorder=True).button_mark_done()
        assert mo.state=='done' and qty(plant,ready)==100
        assert qty(seed,inputs)==0 and qty(substrate,inputs)==0
        assert seed_lot in mo.move_raw_ids.move_line_ids.lot_id
        assert lot in mo.move_finished_ids.move_line_ids.lot_id
        proof.update(finished_units=100,quality_passed=True,traceable_input_output=True,work_orders=2)
    return proof
