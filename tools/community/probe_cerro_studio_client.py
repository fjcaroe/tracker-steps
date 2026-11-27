"""Read Cerro's customized fields through the same RPC methods as Odoo's client."""
import hashlib
import json

from lxml import etree

from probe_cerro_studio_views import inventory, render


def snapshot(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def verify_view(env, operator, row):
    visible = render(env, operator, row)
    assert visible['visible_menu_actions'] and visible['read_existing_record']
    model = env[row['model']].with_user(operator).with_context(
        allowed_company_ids=operator.company_ids.ids, lang='en_US')
    reply = model.get_views([(row['parent'], row['kind'])], options={'toolbar': True, 'load_filters': True})
    arch = etree.fromstring(reply['views'][row['kind']]['arch'].encode())
    legacy = env['ir.ui.view'].browse(row['view_id']).with_context(lang='en_US')
    inserts = etree.fromstring(legacy.arch_db.encode()).xpath('.//field[@name and not(@position)]')
    specification = {'id': {}}
    effective = {}
    for insert in inserts:
        name = insert.get('name')
        matches = arch.xpath('.//field[@name=$name]', name=name)
        if not matches:
            raise ValueError('Field missing from user view: ' + name)
        matched = False
        for node in matches:
            # A nested Studio change can target fields of an O2M subview.
            owner = model
            target = specification
            for parent in reversed(list(node.iterancestors('field'))):
                relation = parent.get('name')
                owner = model.env[owner._fields[relation].comodel_name]
                target = target.setdefault(relation, {}).setdefault('fields', {})
            if name not in owner._fields:
                continue
            if name not in owner.fields_get([name], ['type']):
                raise ValueError('Field unavailable to operator: ' + owner._name + '.' + name)
            effective[owner._name + '.' + name] = owner._fields[name].type
            target[name] = {}
            matched = True
            break
        if not matched:
            raise ValueError('No registered field in user view: ' + name)
    page = model.web_search_read([], specification=specification, limit=1, order='id')
    records = page['records']
    if not records:
        raise ValueError('No existing row for the web client')
    return {'uid': operator.id, 'fields': effective, 'record_id': records[0]['id'],
            'read_sha256': snapshot(records[0]), 'visible_menus': visible['visible_menu_actions']}


def capture(env):
    definitions = inventory(env)
    operator = env['res.users'].browse(6)
    success = {}
    errors = {}
    for alias, row in definitions.items():
        try:
            with env.cr.savepoint():
                success[alias] = verify_view(env, operator, row)
        except Exception as error:
            # This collector is used on an incomplete runtime too. Preserve each
            # specific failure privately so one unavailable model cannot mask the others.
            errors[alias] = {'type': type(error).__name__, 'detail': str(error)[:400]}
    return {'qualified': success, 'errors': errors, 'total': len(definitions)}
