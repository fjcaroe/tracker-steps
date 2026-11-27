"""Compare the native Cerro BoM relation and expense columns under an ordinary manufacturing user."""
import hashlib
import json
import re

from lxml import etree
from odoo.exceptions import AccessError


FIELD = 'x_studio_compaia'
FIELD_ALIAS = 'studio_customization.nuevo_many2one_bill__c2736a42-70d8-4a94-81a7-4c67b9b55714'
VIEWS = (
    ('product.product', 'hr_expense.product_product_expense_categories_tree_view',
     'studio_customization.odoo_studio_product__4e8cc471-cfb4-4b1c-86a3-1974a90d73f8', 'expense_category_accounts'),
    ('product.template', 'account.product_template_view_tree',
     'studio_customization.odoo_studio_product__7a71a49a-898b-40ea-999d-36cc8dd289b3', 'product_template_accounts'),
)
COLS = ('property_account_expense_id', 'categ_id')


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':'), sort_keys=True).encode()).hexdigest()


def reference(env):
    cr = env.cr
    assert re.fullmatch(r'(?:MANAGEMENT_QA|COMMUNITY)_CERRO_BOM_[A-Z0-9_]+', cr.dbname)
    cr.execute("SELECT to_jsonb(b) FROM mrp_bom b ORDER BY id")
    boms = [row[0] for row in cr.fetchall()]
    cr.execute("""SELECT a.id,a.model_id,a.group_id,a.active,a.perm_read,a.perm_write,a.perm_create,a.perm_unlink
                    FROM ir_model_access a JOIN ir_model m ON a.model_id=m.id
                   WHERE m.model IN ('mrp.bom','res.company','product.product','product.template') ORDER BY a.id""")
    access = cr.fetchall()
    cr.execute("""SELECT r.id,r.model_id,r.active,r.domain_force,r.perm_read,r.perm_write,r.perm_create,r.perm_unlink,
                         (SELECT array_agg(group_id ORDER BY group_id) FROM rule_group_rel WHERE rule_group_id=r.id)
                    FROM ir_rule r JOIN ir_model m ON m.id=r.model_id
                   WHERE m.model IN ('mrp.bom','res.company','product.product','product.template') ORDER BY r.id""")
    policies = cr.fetchall()
    cr.execute("""SELECT c.conname,pg_get_constraintdef(c.oid),c.convalidated
                  FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
                  WHERE c.conrelid='mrp_bom'::regclass AND a.attname=%s AND c.contype='f'""", [FIELD])
    fk = cr.fetchall()
    cr.execute("""SELECT f.id,f.ttype,f.relation,f.store,f.required,f.readonly,f.copied,f.on_delete,
                         f.field_description,f.domain,f.company_dependent,d.id,d.noupdate
                    FROM ir_model_fields f JOIN ir_model_data d ON d.model='ir.model.fields' AND d.res_id=f.id
                   WHERE d.module='studio_customization' AND d.name=%s""", [FIELD_ALIAS.split('.')[1]])
    field, = cr.fetchall()
    views = []
    for model, parent, legacy, name in VIEWS:
        view = env.ref(legacy)
        assert view.model == model and view.inherit_id == env.ref(parent)
        cr.execute("SELECT id,model,res_id,noupdate FROM ir_model_data WHERE module=%s AND name=%s", legacy.split('.'))
        views.append((cr.fetchone(), view.id, view.inherit_id.id, view.priority, view.active, view.mode, view.groups_id.ids))
    cr.execute("""SELECT count(DISTINCT v.id) FROM ir_ui_view v JOIN ir_model_data d
                  ON d.model='ir.ui.view' AND d.res_id=v.id AND d.module='studio_customization' WHERE v.active""")
    active = cr.fetchone()[0]
    cr.execute("""SELECT to_jsonb(v) FROM ir_ui_view v WHERE v.active AND
                   EXISTS(SELECT FROM ir_model_data d WHERE d.model='ir.ui.view' AND
                           d.res_id=v.id AND d.module='studio_customization') AND v.id<>ALL(%s)
                   ORDER BY v.id""", [[view[1] for view in views]])
    others = [row[0] for row in cr.fetchall()]
    # Original BoM ID, native company and additional company are compared
    # literally, even on a partial registry with additional SQL columns.
    return {'rows': len(boms), 'values_sha256': digest([(r['id'], r['company_id'], r[FIELD]) for r in boms]),
            'original_studio_populated': sum(r[FIELD] is not None for r in boms),
            'original_native_populated': sum(r['company_id'] is not None for r in boms),
            'field': field, 'fk': fk, 'view_ids': views, 'acl': digest(access), 'rules': digest(policies),
            'studio_views': active, 'other_views': len(others), 'other_view_rows_sha256': digest(others)}


def rendered(env, operator):
    normal = env['mrp.bom'].with_user(operator).with_context(allowed_company_ids=operator.company_ids.ids)
    assert not normal.env.su
    result = {}
    for model, parent, legacy, name in VIEWS:
        records = normal.env[model]
        records.check_access('read')
        records.check_field_access_rights('read', list(COLS))
        arch = etree.fromstring(records.get_view(view_id=env.ref(parent).id, view_type='list')['arch'].encode())
        # A parent may also display a category. Preserve the ordered sequence
        # of the two actual optional columns inserted by this customization.
        found = [(node.get('name'), node.get('optional')) for node in arch.xpath('.//field')
                 if node.get('name') in COLS]
        wanted = list(COLS if name == 'expense_category_accounts' else reversed(COLS))
        assert any(found[index:index+2] == [(n, 'show') for n in wanted] for index in range(len(found)))
        result[name] = found
    return result


def exercise(env, baseline):
    assert json.loads(json.dumps(reference(env))) == baseline['reference']
    assert baseline['reference']['other_views'] == 21
    operator = env['res.users'].browse(baseline['operator'])
    normal = env['mrp.bom'].with_user(operator).with_context(allowed_company_ids=operator.company_ids.ids)
    assert not normal.env.su and operator.has_group('mrp.group_mrp_manager')
    visible = rendered(env, operator)
    assert json.loads(json.dumps(visible)) == baseline['visible']
    native = env.ref(FIELD_ALIAS)
    assert native == env.ref('step_cerro_bom_company.field_mrp_bom__x_studio_compaia') and native.state == 'base'
    for _, _, legacy, name in VIEWS:
        assert env.ref(legacy) == env.ref('step_cerro_product_account_views.' + name)
    field = normal._fields[FIELD]
    assert not field.manual and field.comodel_name == 'res.company' and field.store and field.copy
    assert not field.readonly and not field.required and field.ondelete == 'set null'
    source = normal.search([], order='id', limit=1)
    assert source
    try:
        product = source.product_tmpl_id
        company = normal.env.company
        fresh = normal.create({'product_tmpl_id': product.id, 'product_qty': 1, 'company_id': company.id})
        assert fresh.company_id == company and not fresh[FIELD]
        fresh.write({FIELD: company.id})
        assert fresh[FIELD] == company and fresh.company_id == company
        second = fresh.copy()
        assert second[FIELD] == company
        fresh.write({FIELD: False})
        assert not fresh[FIELD] and fresh.company_id == company
        try:
            fresh.with_user(env.ref('base.public_user')).write({FIELD: company.id})
        except AccessError:
            pass
        else:
            raise AssertionError('Public BoM write unexpectedly allowed')
    finally:
        env.cr.rollback()
    assert json.loads(json.dumps(reference(env))) == baseline['reference']
    return {'operator': operator.id, 'boms': baseline['reference']['rows'], 'active_studio_views': 23,
            'migrated_views': len(visible), 'untouched_views': baseline['reference']['other_views'], 'separate_companies': True, 'copy_preserved': True,
            'access_checked': True, 'rolled_back': True}
