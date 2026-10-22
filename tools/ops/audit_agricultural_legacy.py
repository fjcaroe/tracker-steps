"""Run in an Odoo shell; emit metadata for the cost-center document migration.

Contains no document values. Save output to private artifacts, not to Git.
"""
import json

SEEDS = ['x_riego_y_fertilizacio', 'x_planificar_cosecha', 'x_registro_cosecha',
         'x_sector_de_riego_line_29f4f', 'x_aplicacion_foliar_line_2f222',
         'x_monitoreo_agricola_line_78784', 'x_asesor_externo', 'x_inspecciones_interna']


def audit(env):
    result = {'models': {}, 'group_refs': {str(g.id): g.get_external_id().get(g.id) for g in env['res.groups'].search([])}}
    pending = list(SEEDS)
    while pending:
        name = pending.pop()
        if name in result['models']:
            continue
        model = env[name]
        meta = env['ir.model'].search([('model', '=', name)])
        fields = env['ir.model.fields'].search([('model', '=', name)])
        info = {'state': meta.state, 'description': model._description,
                'table': model._table, 'rec_name': model._rec_name, 'order': model._order,
                'mail_thread': 'message_ids' in model._fields,
                'mail_activity': 'activity_ids' in model._fields,
                'fields': fields.read(['name', 'ttype', 'field_description', 'help',
                                      'relation', 'relation_field', 'required', 'readonly',
                                      'store', 'compute', 'depends', 'related', 'domain',
                                      'state', 'on_delete', 'copied', 'index', 'translate']),
                'count': model.with_context(active_test=False).search_count([])}
        for field in info['fields']:
            native = model._fields.get(field['name'])
            field['runtime_available'] = bool(native)
            if native:
                field.update(runtime_groups=native.groups, runtime_store=native.store,
                             runtime_readonly=native.readonly, runtime_required=native.required,
                             runtime_translate=native.translate)
                if field['ttype'] == 'monetary':
                    field['currency_field'] = native.currency_field
            if native and field['ttype'] == 'selection':
                field['selection'] = native._description_selection(env)
            if native and field['ttype'] == 'many2many':
                field.update(relation_table=native.relation, column1=native.column1,
                             column2=native.column2)
            relation = field['relation']
            if relation and relation.startswith('x_') and not field['name'].startswith(('message_', 'activity_')):
                pending.append(relation)
        result['models'][name] = info
        for key, resource, domain in [
            ('views', 'ir.ui.view', [('model', '=', name)]),
            ('access', 'ir.model.access', [('model_id', '=', meta.id)]),
            ('rules', 'ir.rule', [('model_id', '=', meta.id)]),
            ('automations', 'base.automation', [('model_id', '=', meta.id)]),
            ('actions', 'ir.actions.act_window', [('res_model', '=', name)]),
            ('server_actions', 'ir.actions.server', [('model_id', '=', meta.id)]),
            ('reports', 'ir.actions.report', [('model', '=', name)]),
        ]:
            records = env[resource].with_context(active_test=False).search(domain)
            selected = {
                'views': ['name','model','type','arch_db','inherit_id','priority','active','key'],
                'access': ['name','group_id','perm_read','perm_write','perm_create','perm_unlink'],
                'rules': ['name','domain_force','groups','perm_read','perm_write','perm_create','perm_unlink','active'],
                'automations': ['name','active','trigger','action_server_ids','filter_pre_domain','filter_domain','trigger_field_ids'],
                'actions': ['name','res_model','domain','context','view_mode','view_id','view_ids','search_view_id'],
                'server_actions': ['name','state','code','sequence','model_id','binding_model_id'],
                'reports': ['name','model','report_name','report_file','report_type','binding_model_id'],
            }[key]
            info[key] = records.read(selected)
            refs = records.get_external_id()
            for record in info[key]:
                record['xmlid'] = refs.get(record['id'])
    return result


try:
    print('AGRICULTURAL_LEGACY_AUDIT ' + json.dumps(audit(env), default=str, ensure_ascii=True))
finally:
    env.cr.rollback()
