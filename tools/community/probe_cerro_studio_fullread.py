"""Read every registered field of the compiled Cerro form or list under its original operator."""
import hashlib
import json

from lxml import etree

from probe_cerro_studio_views import inventory


def specification(response, row):
    models = {name: info['fields'] for name, info in response['models'].items()}
    root = etree.fromstring(response['views'][row['kind']]['arch'].encode())
    full = {'id': {}}
    for element in root.xpath('.//field[@name]'):
        scope = row['model']
        current = full
        for field in [*reversed(list(element.iterancestors('field'))), element]:
            name = field.get('name')
            descriptor = models[scope].get(name)
            if descriptor is None:
                raise ValueError('Missing client description: ' + scope + '.' + name)
            request = current.setdefault(name, {})
            if field is not element:
                current = request.setdefault('fields', {})
                if descriptor['type'] in ('one2many', 'many2many'):
                    request.setdefault('limit', 20)
                scope = descriptor['relation']
            elif descriptor['type'] == 'many2one':
                request.setdefault('fields', {'display_name': {}})
    return full


def capture(env):
    actor = env['res.users'].browse(6)
    out = {}
    for alias, row in inventory(env).items():
        try:
            with env.cr.savepoint():
                model = env[row['model']].with_user(actor).with_context(
                    allowed_company_ids=actor.company_ids.ids, lang='en_US')
                reply = model.get_views([(row['parent'], row['kind'])], options={'toolbar': True, 'load_filters': True})
                fields = specification(reply, row)
                result = model.web_search_read([], specification=fields, limit=1, order='id')
                records = result['records']
                if not records:
                    raise ValueError('No visible existing record')
                encoded = json.dumps(records[0], sort_keys=True, default=str).encode()
                out[alias] = {'id': records[0]['id'], 'top_level_fields': len(fields),
                              'value_sha256': hashlib.sha256(encoded).hexdigest()}
        except Exception as error:
            out[alias] = {'error': type(error).__name__, 'detail': str(error)[:400]}
    return out
