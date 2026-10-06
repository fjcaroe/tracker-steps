"""Odoo shell: full Studio metadata/dependency inventory, no business values.

Includes native-model extensions and hidden/archived objects. A manual field
alone is not Studio (analytic plans also create native dynamic fields).
Runtime ownership is inspected to distinguish Python-backed legacy x_ names.
"""
import inspect
import json
import re
from collections import Counter
from psycopg2 import sql
from lxml import etree


def emit(kind, data):
    print(kind + ' ' + json.dumps(data, ensure_ascii=False))


try:
    env.cr.execute('SET TRANSACTION READ ONLY')
    owners = {}
    for row in env['ir.model.data'].sudo().search([]):
        owners.setdefault((row.model, row.res_id), []).append(row.module + '.' + row.name)

    def xmlids(record):
        return sorted(owners.get((record._name, record.id), []))

    def studio(record):
        return any(x.startswith('studio_customization.') for x in xmlids(record))

    metadata = env['ir.model'].sudo().search([])
    manual_models = metadata.filtered(lambda m: m.state == 'manual')
    manual_fields = env['ir.model.fields'].sudo().search([('state', '=', 'manual')])
    candidate_names = set(manual_fields.mapped('name'))
    model_names = set(manual_models.mapped('model'))
    field_counts = Counter(manual_fields.mapped('model'))
    own_modules = set()
    for model in manual_models:
        runtime = env.registry.models.get(model.model)
        python, count = [], None
        if runtime:
            for cls in runtime.__mro__:
                if cls.__module__.startswith('odoo.addons.'):
                    try:
                        filename = inspect.getfile(cls)
                    except (TypeError, OSError):
                        filename = None
                    module = cls.__module__.split('.')[2]
                    python.append({'module': module, 'file': filename})
                    if module.startswith('step_'):
                        own_modules.add(module)
            if runtime._auto and not runtime._abstract:
                env.cr.execute('SELECT to_regclass(%s)', [runtime._table])
                if env.cr.fetchone()[0]:
                    env.cr.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(runtime._table)))
                    count = env.cr.fetchone()[0]
        emit('INVENTORY_MODEL', {'model': model.model, 'name': model.name,
            'xmlids': xmlids(model), 'manual_fields': field_counts[model.model],
            'record_count': count, 'runtime_loaded': bool(runtime), 'python': python})

    for field in manual_fields:
        runtime = env.registry.models.get(field.model)
        descriptor = runtime._fields.get(field.name) if runtime else None
        emit('INVENTORY_FIELD', {'model': field.model, 'name': field.name,
            'label': field.field_description, 'type': field.ttype,
            'relation': field.relation, 'relation_field': field.relation_field,
            'required': field.required, 'readonly': field.readonly,
            'stored': field.store, 'has_compute': bool(field.compute),
            'depends': field.depends, 'xmlids': xmlids(field),
            'runtime_module': getattr(descriptor, '_module', None),
            'runtime_manual': getattr(descriptor, 'manual', None),
            'native_analytic_dynamic': field.name.startswith('x_plan') and field.relation == 'account.analytic.account'})

    def refs(text):
        # Dependency candidates only; expressions may reference related models.
        return sorted(set(re.findall(r'\bx_[A-Za-z0-9_]+\b', text or '')) & (candidate_names | model_names))

    checked_views = set()
    manual_pairs = {(f.model, f.name) for f in manual_fields}
    for view in env['ir.ui.view'].sudo().with_context(active_test=False).search([]):
        references = refs(view.arch_db)
        if not (studio(view) or references or view.model in model_names):
            continue
        root, visited = view, set()
        while root.inherit_id and root.id not in visited:
            visited.add(root.id)
            root = root.inherit_id
        emit('INVENTORY_VIEW', {'id': view.id, 'name': view.name, 'model': view.model,
            'type': view.type, 'active': view.active, 'xmlids': xmlids(view),
            'studio_owner': studio(view), 'parent_id': view.inherit_id.id,
            'root_id': root.id, 'root_xmlids': xmlids(root),
            'groups': view.groups_id.ids, 'reference_candidates': references})
        key = (root.model, root.id, root.type)
        if not (view.active and studio(view) and root.model in env.registry.models
                and root.type in ('form', 'list') and key not in checked_views):
            continue
        checked_views.add(key)
        try:
            with env.cr.savepoint():
                effective = env[root.model].sudo().get_view(view_id=root.id, view_type=root.type)
                tree = etree.fromstring(effective['arch'])
                dependencies = set()

                def walk(node, model_name):
                    current = model_name
                    if node.tag == 'field':
                        field_name = node.get('name')
                        if (model_name, field_name) in manual_pairs:
                            dependencies.add((model_name, field_name))
                        field = env[model_name]._fields.get(field_name)
                        related = getattr(field, 'comodel_name', None) if field else None
                        if related in env.registry.models:
                            current = related
                    for child in node:
                        walk(child, current)

                walk(tree, root.model)
                emit('INVENTORY_EFFECTIVE_VIEW', {'model': root.model, 'id': root.id,
                    'type': root.type, 'manual_dependencies': sorted(dependencies)})
        except Exception as error:
            emit('INVENTORY_EFFECTIVE_ERROR', {'model': root.model, 'id': root.id,
                'type': root.type, 'exception': type(error).__name__})

    # These objects can retain Studio dependencies even if the menu is hidden.
    for model_name, text_fields in [
        ('ir.actions.act_window', ['domain', 'context']),
        ('ir.actions.server', ['code']),
        ('ir.actions.report', ['report_name', 'print_report_name']),
        ('base.automation', ['filter_domain', 'filter_pre_domain']),
        ('ir.model.access', []), ('ir.rule', ['domain_force']),
    ]:
        if model_name not in env.registry.models:
            continue
        model = env[model_name].sudo().with_context(active_test=False)
        for record in model.search([]):
            target = record.res_model if 'res_model' in model._fields else (
                record.model_id.model if 'model_id' in model._fields else (
                    record.model if 'model' in model._fields else None))
            references = sorted(set(r for field in text_fields if field in model._fields for r in refs(record[field])))
            if not (studio(record) or target in model_names or references):
                continue
            data = {'kind': model_name, 'id': record.id, 'name': record.name,
                'target_model': target, 'xmlids': xmlids(record),
                'studio_owner': studio(record), 'reference_candidates': references}
            for field in ['active', 'state', 'binding_model_id', 'action_server_ids', 'group_id', 'groups', 'groups_id']:
                if field not in model._fields:
                    continue
                value = record[field]
                data[field] = value.ids if hasattr(value, 'ids') else value
            emit('INVENTORY_OBJECT', data)

    emit('INVENTORY_SUMMARY', {'manual_models': len(manual_models),
        'manual_fields': len(manual_fields), 'fields_by_model': dict(sorted(field_counts.items())),
        'active_studio_views': env['ir.ui.view'].sudo().search_count([
            ('id', 'in', [key[1] for key, values in owners.items() if key[0] == 'ir.ui.view' and
                any(x.startswith('studio_customization.') for x in values)])]),
        'studio_module_state': env['ir.module.module'].sudo().search_read([
            ('name', 'in', ['web_studio', 'studio_customization'])], ['name', 'state', 'latest_version']),
        'python_modules_on_manual_models': sorted(own_modules)})
    print('STUDIO_INVENTORY_OK')
finally:
    env.cr.rollback()
