"""Check every compiled field of each Cerro screen against its client model metadata."""
from lxml import etree

from probe_cerro_studio_views import inventory


def inspect(env):
    operator = env['res.users'].browse(6)
    results = {}
    for alias, row in inventory(env).items():
        try:
            with env.cr.savepoint():
                model = env[row['model']].with_user(operator).with_context(
                    allowed_company_ids=operator.company_ids.ids, lang='en_US')
                response = model.get_views([(row['parent'], row['kind'])], options={'load_filters': True, 'toolbar': True})
                descriptions = {name: info['fields'] for name, info in response['models'].items()}
                node = etree.fromstring(response['views'][row['kind']]['arch'].encode())
                missing = set()
                fields = set()
                for element in node.xpath('.//field[@name]'):
                    owner = row['model']
                    for parent in reversed(list(element.iterancestors('field'))):
                        ref = descriptions.get(owner, {}).get(parent.get('name'), {})
                        if not ref.get('relation'):
                            owner = None
                            break
                        owner = ref['relation']
                    if owner is None:
                        continue
                    name = element.get('name')
                    fields.add(owner + '.' + name)
                    if name not in descriptions.get(owner, {}):
                        missing.add(owner + '.' + name)
                results[alias] = {'fields': len(fields), 'missing': sorted(missing)}
        except Exception as error:
            results[alias] = {'error': type(error).__name__, 'detail': str(error)[:240]}
    return results
