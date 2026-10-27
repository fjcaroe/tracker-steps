"""T125 approved native category hierarchy; preserve all material/account links."""
import json
from pathlib import Path
import subprocess

CHILDREN = ('6.1 materiales de caja', '6.2 materiales de pallet')
CHANGED = ('parent_id', 'parent_path', 'complete_name', 'write_uid', 'write_date')


def capture(query, database, environment):
    records = json.loads(query(database, "SELECT coalesce(json_agg(to_jsonb(c)),'[]'::json) "
        "FROM product_category c WHERE lower(name) IN ('6 materiales de embalaje',"
        "'6 materiales de embalajes','6.1 materiales de caja','6.2 materiales de pallet')"))
    roots = [r for r in records if r['name'].lower() not in CHILDREN]
    assert len(roots) == 1, 'One native packaging-material root is required'
    children = [r for r in records if r['name'].lower() in CHILDREN]
    if environment in ('development', 'qa-cerro') and not children:
        # Customer QA preserves its own exercise catalog; never import the
        # production subcategories merely to equalize databases.
        return {'root': roots[0]['id'], 'children': [], 'before': [], 'children_absent': True}
    assert len(children) == 2 and {r['name'].lower() for r in children} == set(CHILDREN)
    assert all(r.get('parent_id') in (None, False, roots[0]['id']) for r in children), 'Unexpected existing parent'
    ids = sorted(r['id'] for r in children)
    assert query(database, 'SELECT count(*) FROM product_category WHERE parent_id IN (%s)' %
                 ','.join(map(str, ids))) == '0', 'New descendant categories require an expanded preservation plan'
    return {'root': roots[0]['id'], 'children': ids, 'before': sorted(records, key=lambda r: r['id'])}


def snapshot_row(row, plan):
    if not plan['children']:
        return row
    identifiers = ','.join(str(int(i)) for i in plan['children'])
    columns = ','.join("'%s'" % name for name in CHANGED)
    return 'CASE WHEN t.id IN (%s) THEN (%s-ARRAY[%s]) ELSE %s END' % (identifiers, row, columns, row)


def apply(env, plan):
    if not plan['children']:
        return {'changed': 0, 'children': [], 'children_absent': True, 'accounts_preserved': True, 'category_ids_preserved': True}
    Category = env['product.category']
    root = Category.browse(plan['root']).exists()
    children = Category.browse(plan['children']).exists()
    assert len(root) == 1 and len(children) == 2
    assert {c.name.lower() for c in children} == set(CHILDREN)
    assert all(not c.parent_id or c.parent_id == root for c in children)
    assert not children.child_id
    env.cr.execute('SELECT id,to_jsonb(c) FROM product_category c ORDER BY id')
    before = dict(env.cr.fetchall())
    for original in plan['before']:
        assert before.get(original['id']) == original, 'Category changed since the tested configuration plan'
    products = env['product.template'].search([('categ_id', 'in', children.ids)])
    product_categories = {p.id: p.categ_id.id for p in products}

    def accounts():
        result = {}
        for company in env['res.company'].search([]):
            for product in products.filtered(lambda p: not p.company_id or p.company_id == company):
                result[(company.id, product.id)] = {
                    key: getattr(value, 'ids', value)
                    for key, value in product.with_company(company).get_product_accounts().items()}
        return result

    original_accounts = accounts()
    changed = children.filtered(lambda c: c.parent_id != root)
    changed.write({'parent_id': root.id})
    env.flush_all()
    env.invalidate_all()
    assert accounts() == original_accounts, 'The category hierarchy changed effective accounting'
    assert {p.id: p.categ_id.id for p in products} == product_categories
    assert all(c.parent_id == root and c.parent_path == root.parent_path + str(c.id) + '/'
               and c.complete_name.startswith(root.complete_name) and c.complete_name.endswith(c.name) for c in children)
    env.cr.execute('SELECT id,to_jsonb(c) FROM product_category c ORDER BY id')
    after = dict(env.cr.fetchall())
    assert before.keys() == after.keys(), 'Category identities changed'
    for ident in before:
        ignored = set(CHANGED) if ident in children.ids else set()
        assert {k: v for k, v in before[ident].items() if k not in ignored} == {
            k: v for k, v in after[ident].items() if k not in ignored}, 'Unexpected master change'
    return {'changed': len(changed), 'root': root.id, 'children': children.ids,
            'products_preserved': len(products), 'accounts_preserved': True, 'category_ids_preserved': True}


def configure(base, options, database, source, opts, stage, plan):
    script = 'import sys\nsys.path.insert(0,%r)\n' % str(Path(__file__).resolve().parent)
    script += 'from packing_material_hierarchy_setup import apply\nimport json\n'
    script += 'result=apply(env,%r)\nenv.cr.commit()\nprint("T125_HIERARCHY_CONFIGURED "+json.dumps(result))\n' % plan
    data = ['--data-dir=' + str(stage / 'data')] if database.startswith('MANAGEMENT_QA_') else []
    result = subprocess.run(base + ['shell'] + options + data + ['-d', database,
        '--addons-path=' + str(source) + ',' + opts['addons_path'], '--log-level=error'],
        input=script, text=True, capture_output=True)
    (stage / ('material-hierarchy-' + database + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'T125_HIERARCHY_CONFIGURED ' in result.stdout, result.stderr[-2500:]
    print(next(line for line in result.stdout.splitlines() if line.startswith('T125_HIERARCHY_CONFIGURED ')), flush=True)
