"""Odoo shell: read actual menu/view/model ownership, never business values.

Run using run_app_audit.py --studio. Legacy x_ names alone are not proof
of Studio: Python-backed fields may retain them to preserve record IDs.
Manual fields can also be native dynamic fields (e.g. analytic plan columns).
View inheritance candidates are inspected with administrative access; this
does not certify each operator's rendered fields or functional workflow.
Menu visibility uses the real loaded tree for every active internal user.
"""
import inspect
import json
from lxml import etree


def emit(kind, data):
    print(kind + ' ' + json.dumps(data, ensure_ascii=False))


try:
    # Fail closed if any ORM path attempts a database mutation.
    env.cr.execute('SET TRANSACTION READ ONLY')
    Menu = env['ir.ui.menu'].sudo().with_context(**{'ir.ui.menu.full_list': True})
    menus = Menu.search([('active', '=', True)])
    owners = {}
    for row in env['ir.model.data'].sudo().search([
        ('model', 'in', ['ir.ui.menu', 'ir.ui.view', 'ir.actions.act_window'])
    ]):
        owners.setdefault((row.model, row.res_id), []).append(row.module + '.' + row.name)

    def xmlids(record):
        return sorted(owners.get((record._name, record.id), []))

    group = env.ref('base.group_user')
    users = env['res.users'].sudo().search([('active', '=', True), ('share', '=', False)])
    users = users.filtered(lambda u: group in u.groups_id)
    admins = users.filtered(lambda u: env.ref('base.group_system') in u.groups_id)
    ordinary = users - admins
    visible = {'administrator': set(), 'internal': set()}
    for role, records in [('administrator', admins), ('internal', ordinary)]:
        for user in records:
            # The ACL-visible set can contain detached children whose parent
            # is restricted. load_menus removes those from the rendered tree.
            loaded = env['ir.ui.menu'].with_user(user).load_menus(False)
            visible[role].update(key for key in loaded if isinstance(key, int))

    roots = set()
    modules = ('step_hr', 'step_cosecha', 'step_packing', 'step_packing_operations',
               'step_export', 'step_producers', 'step_sawmill',
               'step_management_costs', 'step_operations_ui')
    for menu in menus.filtered(lambda m: not m.parent_id):
        if any(x.split('.')[0] in modules + ('studio_customization',) for x in xmlids(menu)) or any(
            word in menu.name.lower() for word in ('packing', 'export', 'productor',
                'aserradero', 'cosecha', 'flete', 'actividad', 'gestión y costos')
        ):
            roots.add(menu.id)
    scoped = Menu.search([('id', 'child_of', list(roots)), ('active', '=', True)])
    actions = {}
    for menu in scoped:
        chain, cursor = [], menu
        while cursor:
            chain.append(cursor)
            cursor = cursor.parent_id
        chain.reverse()
        historical = any('Historial anterior' in m.name for m in chain)
        action = menu.action
        model = action.res_model if action and action._name == 'ir.actions.act_window' else None
        row = {'id': menu.id, 'path': ' / '.join(m.name for m in chain),
               'xmlids': xmlids(menu), 'historical': historical,
               'visible_internal': menu.id in visible['internal'],
               'visible_administrator': menu.id in visible['administrator'],
               'action_xmlids': xmlids(action) if action else [], 'model': model}
        emit('STUDIO_MENU', row)
        if model:
            actions.setdefault(action.id, (action, []) )[1].append(row)

    metadata = env['ir.model'].sudo().search([])
    model_states = {r.model: r.state for r in metadata}
    fields = env['ir.model.fields'].sudo().search([('state', '=', 'manual')])
    manual = {}
    for field in fields:
        manual.setdefault(field.model, set()).add(field.name)
    # Include unported screens outside the named product roots. This catches
    # standalone Studio apps without assuming their titles or XML IDs.
    for menu in menus - scoped:
        action = menu.action
        if not action or action._name != 'ir.actions.act_window':
            continue
        if model_states.get(action.res_model) != 'manual':
            continue
        if menu.id not in visible['internal'] | visible['administrator']:
            continue
        chain, cursor = [], menu
        while cursor:
            chain.append(cursor.name)
            cursor = cursor.parent_id
        emit('STUDIO_OTHER_MANUAL_MENU', {'id': menu.id,
            'path': ' / '.join(reversed(chain)), 'model': action.res_model,
            'xmlids': xmlids(menu), 'visible_internal': menu.id in visible['internal'],
            'visible_administrator': menu.id in visible['administrator']})
    seen = set()
    for action, action_menus in actions.values():
        model_name = action.res_model
        if model_name not in env.registry.models:
            emit('STUDIO_MISSING_MODEL', {'model': model_name, 'action': action.id})
            continue
        model = env[model_name].sudo().with_context(lang=None)
        python = []
        for cls in type(model).__mro__:
            if cls.__module__.startswith('odoo.addons.'):
                try:
                    filename = inspect.getfile(cls)
                except (TypeError, OSError):
                    filename = None
                python.append({'module': cls.__module__, 'file': filename})
        if model_name not in seen:
            emit('STUDIO_MODEL', {'model': model_name, 'state': model_states.get(model_name),
                'manual_fields': sorted(manual.get(model_name, set())), 'python': python})
            seen.add(model_name)
        for view_id, view_type in action.views:
            if view_type not in ('form', 'list', 'kanban'):
                continue
            key = (model_name, view_id, view_type)
            if key in seen:
                continue
            seen.add(key)
            try:
                result = model.get_view(view_id=view_id or None, view_type=view_type)
                base = env['ir.ui.view'].sudo().browse(result['id'])
                tree = etree.fromstring(result['arch'])
                # Top-level fields belong to this model; nested x2many fields
                # must be resolved against their related model separately.
                nodes = tree.xpath('//field[not(ancestor::field)]')
                top_fields = sorted(set(n.get('name') for n in nodes if n.get('name')))
                effective_manual = sorted(set(top_fields) & manual.get(model_name, set()))
                nested_manual = []

                def inspect_nested(node, current_model):
                    for child in node:
                        next_model = current_model
                        if child.tag == 'field':
                            name = child.get('name')
                            if current_model != model_name and name in manual.get(current_model, set()):
                                nested_manual.append({'model': current_model, 'field': name})
                            field = env[current_model]._fields.get(name)
                            related = getattr(field, 'comodel_name', None) if field else None
                            if related in env.registry.models:
                                next_model = related
                        inspect_nested(child, next_model)

                inspect_nested(tree, model_name)
                view_chain, pending = {}, [base]
                while pending:
                    parent = pending.pop()
                    if parent.id in view_chain:
                        continue
                    view_chain[parent.id] = parent
                    # Studio inheritance may be above the primary view too.
                    if parent.inherit_id:
                        pending.append(parent.inherit_id)
                    pending.extend(env['ir.ui.view'].sudo().search([
                        ('inherit_id', '=', parent.id), ('active', '=', True),
                        ('mode', '=', 'extension')]))
                studio = [{'id': v.id, 'xmlids': xmlids(v), 'name': v.name,
                           'groups': v.groups_id.ids} for v in view_chain.values()
                          if any(x.startswith('studio_customization.') for x in xmlids(v))]
                emit('STUDIO_VIEW', {'model': model_name, 'type': view_type,
                    'id': base.id, 'xmlids': xmlids(base), 'action': action.id,
                    'menu_paths': [m['path'] for m in action_menus],
                    'visible_internal': any(m['visible_internal'] for m in action_menus),
                    'historical_only': all(m['historical'] for m in action_menus),
                    'effective_manual_fields': effective_manual,
                    'nested_manual_fields': nested_manual,
                    'legacy_named_fields': [f for f in top_fields if f.startswith('x_')],
                    'studio_inheritance_candidates': studio})
            except Exception as error:
                # Do not include exception text: business values may appear there.
                emit('STUDIO_VIEW_ERROR', {'model': model_name, 'type': view_type,
                    'action': action.id, 'exception': type(error).__name__})

    emit('STUDIO_SUMMARY', {'users_examined': len(users), 'internal_users': len(ordinary),
        'scoped_menus': len(scoped), 'models_examined': len([x for x in seen if isinstance(x, str)]),
        'active_studio_views': env['ir.ui.view'].sudo().search_count([
            ('active', '=', True), ('id', 'in', [key[1] for key, values in owners.items()
                if key[0] == 'ir.ui.view' and any(v.startswith('studio_customization.') for v in values)])]),
        'installed': env['ir.module.module'].sudo().search_read([
            ('name', 'in', list(modules)), ('state', '=', 'installed')], ['name', 'latest_version'])})
    print('STUDIO_AUDIT_OK')
finally:
    env.cr.rollback()
