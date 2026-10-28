"""T127 transactional in-place conversion; no copied catalog or guessed values."""
import argparse
import hashlib
import json
from pathlib import Path
from psycopg2 import sql

MODULE = 'step_product_bpa'
OLD = 'x_aptitud_plaguicidas'
NEW = 'step.agriculture.pesticide.aptitude'
MODEL_FIELDS = {'x_name': 'name', 'x_active': 'active', 'x_studio_cdigo_aptitud': 'code',
                'x_studio_observacin': 'notes', 'x_studio_sequence': 'sequence'}
PRODUCT_FIELDS = {'x_studio_concentracin': 'registration_concentration',
    'x_studio_formulacin': 'registration_formulation', 'x_studio_cdigo_formulacin': 'registration_formulation_code',
    'x_studio_aptitud_plaguicida': 'registration_aptitude_id',
    'x_studio_titular_autorizacin': 'registration_authorization_holder',
    'x_studio_primera_autorizacin': 'registration_first_authorized_on',
    'x_studio_vencimiento_autorizacin': 'registration_authorization_expires_on'}


def exists(cr, table):
    cr.execute('SELECT to_regclass(%s)', (table,))
    return bool(cr.fetchone()[0])


def columns(cr, table):
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY column_name", (table,))
    return [r[0] for r in cr.fetchall()]


def adopt(cr, model, ident, alias):
    cr.execute("SELECT module,name FROM ir_model_data WHERE model=%s AND res_id=%s AND module<>%s", (model, ident, MODULE))
    for mod, name in cr.fetchall():
        cr.execute('UPDATE ir_model_data SET module=%s,name=%s,noupdate=TRUE WHERE module=%s AND name=%s',
                   (MODULE, 'legacy_' + mod + '_' + name, mod, name))
    cr.execute('SELECT model,res_id FROM ir_model_data WHERE module=%s AND name=%s', (MODULE, alias))
    found = cr.fetchone()
    assert not found or found == (model, ident), ('Conflicting migration alias', alias)
    if not found:
        cr.execute('INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES(%s,%s,%s,%s,TRUE)', (MODULE, alias, model, ident))


def prepare(cr):
    from lxml import etree
    old_table, new_table = OLD, NEW.replace('.', '_')
    assert not (exists(cr, old_table) and exists(cr, new_table)), 'Parallel masters require reconciliation'
    cr.execute('SELECT id,name FROM ir_model_fields WHERE model=%s AND name LIKE %s', (OLD, 'x_%'))
    assert {name for _, name in cr.fetchall()} <= set(MODEL_FIELDS), 'Unknown Studio aptitude fields'
    cr.execute('SELECT id FROM ir_model WHERE model=%s', (OLD,))
    model = cr.fetchone()
    if model:
        if exists(cr, 'base_automation'):
            cr.execute('SELECT id FROM base_automation WHERE model_id=%s AND active', (model[0],))
            assert not cr.fetchall(), 'Active aptitude automation must be converted to code first'
        cr.execute(sql.SQL('ALTER TABLE {} RENAME TO {}').format(sql.Identifier(old_table), sql.Identifier(new_table)))
        if exists(cr, old_table + '_id_seq'):
            cr.execute(sql.SQL('ALTER SEQUENCE {} RENAME TO {}').format(sql.Identifier(old_table+'_id_seq'), sql.Identifier(new_table+'_id_seq')))
        adopt(cr, 'ir.model', model[0], 'model_' + new_table)
        cr.execute('SELECT id,group_id FROM ir_model_access WHERE model_id=%s', (model[0],))
        for ident, group in cr.fetchall():
            cr.execute('SELECT name FROM ir_model_data WHERE model=%s AND res_id=%s AND module=%s', ('res.groups', group, 'base'))
            group_xmlid = cr.fetchone()
            alias = {'group_user':'access_aptitude_user', 'group_system':'access_aptitude_system'}.get(group_xmlid[0] if group_xmlid else '')
            adopt(cr, 'ir.model.access', ident, alias or 'legacy_access_' + str(ident))
        cr.execute('SELECT id FROM ir_ui_view WHERE model=%s', (OLD,))
        for (ident,) in cr.fetchall():
            adopt(cr, 'ir.ui.view', ident, 'legacy_view_' + str(ident))
        cr.execute('UPDATE ir_ui_view SET active=FALSE WHERE model=%s', (OLD,))
    for original, target, mapping in [(OLD, new_table, MODEL_FIELDS), ('product.template', 'product_template', PRODUCT_FIELDS)]:
        for old, new in mapping.items():
            cr.execute('SELECT id FROM ir_model_fields WHERE model=%s AND name=%s', (original, old))
            field = cr.fetchone()
            if not field:
                continue
            cols = columns(cr, target)
            assert old in cols and new not in cols, ('Conflicting field migration', target, old, new)
            cr.execute(sql.SQL('ALTER TABLE {} RENAME COLUMN {} TO {}').format(sql.Identifier(target), sql.Identifier(old), sql.Identifier(new)))
            cr.execute("UPDATE ir_model_fields SET name=%s,state='base' WHERE id=%s", (new, field[0]))
            adopt(cr, 'ir.model.fields', field[0], 'field_' + target + '__' + new)
    # Model identity columns include chatter, attachments, activities, exports,
    # references and original actions. Numeric model_id references keep their IDs.
    cr.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND data_type IN ('text','character varying') AND column_name IN ('model','model_name','res_model','res_model_name','model_id','application_model')")
    for table, col in cr.fetchall():
        cr.execute(sql.SQL('UPDATE {} SET {}=%s WHERE {}=%s').format(sql.Identifier(table), sql.Identifier(col), sql.Identifier(col)), (NEW, OLD))
    cr.execute("UPDATE ir_model SET state='base' WHERE model=%s", (NEW,))
    cr.execute("UPDATE ir_model_fields SET state='base' WHERE model=%s", (NEW,))
    cr.execute('UPDATE ir_model_fields SET relation=%s WHERE relation=%s', (NEW, OLD))
    cr.execute('SELECT id FROM ir_model_fields WHERE model=%s', (NEW,))
    for (ident,) in cr.fetchall():
        cr.execute('SELECT name FROM ir_model_fields WHERE id=%s', (ident,))
        adopt(cr, 'ir.model.fields', ident, 'field_' + new_table + '__' + cr.fetchone()[0])
    # Remove only this feature's Studio insertions; unrelated Studio features
    # retain their views. The versioned views become the only owners of T127 UI.
    retired = set(PRODUCT_FIELDS) | set(PRODUCT_FIELDS.values()) | {'agriculture_active_ingredient_id', 'agriculture_max_applications', 'agriculture_max_withholding_days', 'agriculture_eu_withholding_days', 'agriculture_us_withholding_days'}
    cr.execute("SELECT id,arch_db FROM ir_ui_view WHERE model='product.template' AND name LIKE 'Odoo Studio:%'")
    for ident, translations in cr.fetchall():
        result = {}
        for lang, arch in translations.items():
            tree = etree.fromstring(arch)
            for node in list(tree.xpath('.//field')):
                if node.get('name') in retired:
                    node.getparent().remove(node)
            for node in list(tree):
                if node.tag == 'xpath' and len(node) == 0 and not (node.text or '').strip():
                    tree.remove(node)
            result[lang] = etree.tostring(tree, encoding='unicode')
        cr.execute('UPDATE ir_ui_view SET arch_db=%s::jsonb WHERE id=%s', (json.dumps(result), ident))
    # Translate field paths and saved expressions, preserving their identities.
    import re
    def translate(value, aptitude=False):
        mapping = {OLD: NEW, **PRODUCT_FIELDS}
        if aptitude: mapping.update(MODEL_FIELDS)
        if not value: return value
        for old, new in sorted(mapping.items(), key=lambda item: -len(item[0])):
            value = re.sub(r'(?<![A-Za-z0-9_])' + re.escape(old) + r'(?![A-Za-z0-9_])', lambda match: new, value)
        return value
    targets = [('ir_model_fields','related'),('ir_model_fields','depends'),('ir_act_window','domain'),('ir_act_window','context'),('ir_rule','domain_force'),('ir_filters','domain'),('ir_filters','context'),('ir_act_server','code')]
    for table, col in targets:
        if not exists(cr, table) or col not in columns(cr, table): continue
        if table == 'ir_model_fields':
            scope = "model"
        elif table == 'ir_act_window':
            scope = "res_model"
        elif table == 'ir_filters':
            scope = "model_id"
        else:
            scope = "(SELECT model FROM ir_model WHERE id=t.model_id)"
        cr.execute(sql.SQL('SELECT id,{},' + scope + ' FROM {} t WHERE {} IS NOT NULL').format(sql.Identifier(col),sql.Identifier(table),sql.Identifier(col)))
        for ident, value, resource_model in cr.fetchall():
            updated = translate(value, aptitude=resource_model == NEW)
            if updated != value:
                cr.execute(sql.SQL('UPDATE {} SET {}=%s WHERE id=%s').format(sql.Identifier(table),sql.Identifier(col)), (updated,ident))


def finalize(cr):
    new_table = NEW.replace('.', '_')
    cr.execute('SELECT id FROM ir_act_window WHERE res_model=%s', (NEW,))
    for (ident,) in cr.fetchall():
        adopt(cr, 'ir.actions.act_window', ident, 'legacy_action_' + str(ident))
        cr.execute("SELECT res_id FROM ir_model_data WHERE module=%s AND name='view_aptitude_form'", (MODULE,))
        form = cr.fetchone()[0]
        cr.execute("SELECT res_id FROM ir_model_data WHERE module=%s AND name='view_aptitude_search'", (MODULE,))
        search = cr.fetchone()[0]
        cr.execute("UPDATE ir_act_window SET view_mode='list,form',view_id=NULL,search_view_id=%s WHERE id=%s", (search,ident))
        cr.execute('DELETE FROM ir_act_window_view WHERE act_window_id=%s', (ident,))
    cr.execute('SELECT count(*) FROM ir_model_fields WHERE model=%s AND state=%s', (NEW,'manual'))
    assert cr.fetchone()[0] == 0


def snapshot(cr, baseline):
    if not baseline:
        cr.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%%' OR tablename LIKE 'product_%%' OR tablename LIKE 'stock_%%' OR tablename LIKE 'account_%%' OR tablename LIKE 'hr_%%' OR tablename IN ('x_aptitud_plaguicidas','res_company','res_partner','res_partner_bank','mail_message','mail_followers','mail_activity','mail_tracking_value','ir_attachment')) ORDER BY tablename")
        baseline.update({table: columns(cr, table) for (table,) in cr.fetchall()})
    result = {}
    for logical, cols in baseline.items():
        table = NEW.replace('.', '_') if logical == OLD and not exists(cr, OLD) else logical
        actual = columns(cr, table)
        fields = MODEL_FIELDS if logical in (OLD, NEW.replace('.', '_')) else PRODUCT_FIELDS if logical=='product_template' else {}
        pairs = []
        for old in cols:
            col = old if old in actual else fields.get(old, old)
            assert col in actual, ('Lost original column', table, old)
            value = sql.SQL('t.{}').format(sql.Identifier(col))
            if old in ('res_model','model'):
                value = sql.SQL('CASE WHEN t.{}=%s THEN %s ELSE t.{} END').format(sql.Identifier(col),sql.Identifier(col))
            pairs.extend([sql.Literal(old), value])
        expr = sql.SQL(' || ').join(sql.SQL('jsonb_build_object({})').format(sql.SQL(',').join(pairs[i:i+80])) for i in range(0,len(pairs),80))
        statement = sql.SQL('SELECT count(*),md5(coalesce(string_agg(row::text,\'\' ORDER BY row::text),\'\')) FROM (SELECT {} row FROM {} t) records').format(expr,sql.Identifier(table))
        params = [item for old in cols if old in ('res_model','model') for item in (OLD,NEW)]
        cr.execute(statement,params)
        result[logical] = cr.fetchone()
    return result


def main():
    import psycopg2
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','finalize','snapshot']);p.add_argument('database');p.add_argument('--baseline',type=Path)
    a=p.parse_args()
    with psycopg2.connect(dbname=a.database,user='postgres') as conn:
        with conn.cursor() as cr:
            if a.action=='snapshot':
                baseline=json.loads(a.baseline.read_text()) if a.baseline.exists() else {}
                data=snapshot(cr,baseline);a.baseline.write_text(json.dumps(baseline));print(json.dumps(data))
            else:
                globals()[a.action](cr);print('BPA_'+a.action.upper()+'_OK')

if __name__=='__main__': main()
