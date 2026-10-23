"""Read application menus and additive model ACLs without inspecting users."""
import json

try:
    roots = env['ir.ui.menu'].with_context(**{'ir.ui.menu.full_list':True}).search([('parent_id','=',False)])
    names = ('A dónde va la lancha','Packing','Exportaciones','Task','Productores','Harvest')
    selected = roots.filtered(lambda menu: menu.with_context(lang='es_CL').name in names
                              or menu.with_context(lang='en_US').name in names)
    def ids(records):
        external = records.get_external_id()
        return [external.get(record.id) or '%s,%s'%(record._name,record.id) for record in records]
    results = []
    for root in selected:
        menus = env['ir.ui.menu'].search([('id','child_of',root.id)])
        rows=[]
        models=set()
        for menu in menus:
            action=menu.action
            model=action.res_model if action and action._name=='ir.actions.act_window' else None
            if model:models.add(model)
            rows.append({'menu':ids(menu)[0],'name':menu.with_context(lang='es_CL').name,
                         'groups':ids(menu.groups_id),'action_type':action._name if action else None,
                         'model':model,'client_tag':action.tag if action and action._name=='ir.actions.client' else None})
        access=env['ir.model.access'].search([('active','=',True),('model_id.model','in',sorted(models))])
        results.append({'root':ids(root)[0],'name':root.with_context(lang='es_CL').name,
            'menus':rows,'access':[{'acl':ids(acl)[0],'model':acl.model_id.model,
                'group':ids(acl.group_id)[0] if acl.group_id else None,
                'read':acl.perm_read,'write':acl.perm_write,'create':acl.perm_create,'unlink':acl.perm_unlink}
                for acl in access]})
    print('APPLICATION_ACCESS_INVENTORY '+json.dumps({'database':env.cr.dbname,'applications':results},ensure_ascii=False))
finally:
    env.cr.rollback()
