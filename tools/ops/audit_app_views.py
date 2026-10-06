"""Odoo shell metadata audit of actual agriculture menus/forms; no record data."""
import json
from lxml import etree

roots = ('step_hr.menu_step_hr_root','step_cosecha.menu_step_cosecha_root',
         'step_export.menu_step_export_root','step_producers.menu_step_producers_root',
         'step_packing.menu_step_packing_root','step_packing.menu_packing_fruta_root')
try:
    models = set()
    for xmlid in roots:
        root = env.ref(xmlid,raise_if_not_found=False)
        if not root:
            continue
        menus = env['ir.ui.menu'].search([('id','child_of',root.id)])
        rows=[]
        for menu in menus:
            action=menu.action
            model=action.res_model if action and action._name=='ir.actions.act_window' else None
            if model: models.add(model)
            ids=menu.get_external_id()
            rows.append({'id':menu.id,'name':menu.name,'parent':menu.parent_id.id,'xmlid':ids.get(menu.id),'model':model})
        print('APP_MENUS '+json.dumps({'root':xmlid,'menus':rows},ensure_ascii=False))
    for name in sorted(models):
        if name not in env.registry.models:
            print('APP_MISSING_MODEL '+name)
            continue
        model=env[name]
        arch=model.get_view(view_type='form')['arch']
        visible=etree.fromstring(arch).xpath('//field[not(@invisible="1") and not(@invisible="True")]')
        fields=[]
        for node in visible:
            field=model._fields.get(node.get('name'))
            if field and not field.readonly:
                fields.append({'name':field.name,'type':field.type,'relation':getattr(field,'comodel_name',None),'studio':field.name.startswith('x_')})
        print('APP_FORM '+json.dumps({'model':name,'fields':fields},ensure_ascii=False))
    print('APP_AUDIT_OK')
finally: env.cr.rollback()
