"""Transactional, in-place agricultural migration, executed before registry load.

The publisher runs this exact file from the immutable tested package. It never
copies business rows into a second model or reconstructs links from labels.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re

from psycopg2 import sql


def source(name):
    spec = importlib.util.spec_from_file_location('agriculture_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCHEMA = source('schema')
MODELS = SCHEMA.MODELS
FIELDS = {**source('field_names').FIELDS, **SCHEMA.FOREIGN_FIELDS}
ADOPTIONS = source('adoption').ADOPTIONS
MODULE = 'step_agriculture_records'


def table_name(model):
    return model.replace('.', '_')


def exists(cr, table):
    cr.execute('SELECT to_regclass(%s)', (table,))
    return bool(cr.fetchone()[0])


def column_exists(cr, table, column):
    cr.execute('SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=\'public\' '
               'AND table_name=%s AND column_name=%s)', (table, column))
    return cr.fetchone()[0]


def reference(cr, xmlid):
    module, name = xmlid.split('.', 1)
    cr.execute('SELECT model,res_id FROM ir_model_data WHERE module=%s AND name=%s', (module, name))
    return cr.fetchone()


def alias(cr, name, model, res_id):
    found = reference(cr, MODULE + '.' + name)
    assert not found or found == (model, res_id), ('Conflicting migration alias', name)
    if not found:
        cr.execute('INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES(%s,%s,%s,%s,TRUE)',
                   (MODULE, name, model, res_id))


def adopt(cr, xmlid, name):
    found = reference(cr, xmlid)
    if not found:
        # The source XMLID was adopted by a previous release. A later native
        # update must verify/reuse that identity rather than require Studio.
        found = reference(cr, MODULE + '.' + name)
        assert found, ('Missing audited metadata and adopted identity', xmlid)
        return
    assert found, ('Missing audited metadata', xmlid)
    old_module, old_name = xmlid.split('.', 1)
    alias(cr, name, *found)
    if old_module != MODULE:
        cr.execute('UPDATE ir_model_data SET module=%s,name=%s,noupdate=TRUE WHERE module=%s AND name=%s',
                   (MODULE, 'legacy_' + old_module + '_' + old_name, old_module, old_name))


def field_catalog(cr):
    cr.execute('SELECT id,model,name,relation,related,depends FROM ir_model_fields')
    return {(model, name): {'id': ident, 'relation': relation, 'related': related, 'depends': depends}
            for ident, model, name, relation, related, depends in cr.fetchall()}


def translate_path(model, path, catalog):
    translated = []
    for piece in path.split('.'):
        translated.append(FIELDS.get(model, {}).get(piece, piece))
        field = catalog.get((model, piece), {})
        model = field.get('relation') or ''
    return '.'.join(translated)


def expression(model, value):
    if not value:
        return value
    mapping = FIELDS.get(model, {})
    mapping = {**mapping, **{'default_' + k: 'default_' + v for k, v in mapping.items()},
               **{'search_default_' + k: 'search_default_' + v for k, v in mapping.items()}}
    return SCHEMA.replace_tokens(SCHEMA.replace_tokens(value, MODELS), mapping) if mapping else SCHEMA.replace_tokens(value, MODELS)


def prepare(cr):
    catalog = field_catalog(cr)
    present = {model for model, name in catalog}
    preserve_existing_access(cr)
    for old in MODELS:
        seen = {name for model, name in catalog if model == old and name.startswith('x_')}
        assert not seen or seen == set(FIELDS[old]), ('Concurrent agricultural schema change', old)
    before = {}
    for old, new in MODELS.items():
        source_table, target = table_name(old), table_name(new)
        old_exists, new_exists = exists(cr, source_table), exists(cr, target)
        assert not (old_exists and new_exists), ('Parallel tables; manual reconciliation required', old)
        if not old_exists and not new_exists:
            assert old not in present and new not in present, ('Missing table of an existing model', old)
            continue  # The ORM creates a new empty native model, not a copy.
        if not old_exists:
            continue
        cr.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(source_table)))
        before[old] = cr.fetchone()[0]
        cr.execute(sql.SQL('ALTER TABLE {} RENAME TO {}').format(sql.Identifier(source_table), sql.Identifier(target)))
        if exists(cr, source_table + '_id_seq'):
            cr.execute(sql.SQL('ALTER SEQUENCE {} RENAME TO {}').format(
                sql.Identifier(source_table + '_id_seq'), sql.Identifier(target + '_id_seq')))
    for old_model, mapping in FIELDS.items():
        target = table_name(MODELS.get(old_model, old_model))
        for old, new in mapping.items():
            if column_exists(cr, target, old):
                assert not column_exists(cr, target, new), ('Parallel fields', target, old, new)
                cr.execute(sql.SQL('ALTER TABLE {} RENAME COLUMN {} TO {}').format(
                    sql.Identifier(target), sql.Identifier(old), sql.Identifier(new)))
            field = catalog.get((old_model, old))
            if field:
                cr.execute("UPDATE ir_model_fields SET name=%s,state='base' WHERE id=%s", (new, field['id']))
    for (model, name), field in catalog.items():
        if field['related']:
            translated = translate_path(model, field['related'], catalog)
            if translated != field['related']:
                cr.execute('UPDATE ir_model_fields SET related=%s WHERE id=%s', (translated, field['id']))
        if field['depends'] and model in FIELDS:
            translated = ','.join(translate_path(model, path.strip(), catalog) for path in field['depends'].split(','))
            cr.execute('UPDATE ir_model_fields SET depends=%s WHERE id=%s', (translated, field['id']))
    for model, mapping in SCHEMA.FOREIGN_FIELDS.items():
        for old_name, new_name in mapping.items():
            field = catalog.get((model, old_name))
            if not field:
                continue
            cr.execute("SELECT module,name FROM ir_model_data WHERE model='ir.model.fields' AND res_id=%s AND module<>%s",
                       (field['id'], MODULE))
            for mod, name in cr.fetchall():
                adopt(cr, mod + '.' + name, 'legacy_ref_' + mod + '_' + name)
            alias(cr, 'field_' + table_name(model) + '__' + new_name, 'ir.model.fields', field['id'])
    # Preserve model/field IDs, delegated fields, chatter, attachments and all
    # metadata with an explicit model-name column, not just ir.model itself.
    cr.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' "
               "AND data_type IN ('text','character varying') AND column_name IN "
               "('model','model_name','res_model','res_model_name','model_id','application_model')")
    references = [(table, column) for table, column in cr.fetchall() if table != 'ir_model_fields_selection']
    for old, new in MODELS.items():
        cr.execute('SELECT id FROM ir_model WHERE model IN (%s,%s)', (old, new))
        rows = cr.fetchall()
        if not rows:
            continue
        assert len(rows) == 1, ('Ambiguous model metadata', old)
        model_id = rows[0][0]
        cr.execute('SELECT id FROM ir_model_fields WHERE model IN (%s,%s)', (old, new))
        field_ids = [row[0] for row in cr.fetchall()]
        for resource, ids in [('ir.model', [model_id]), ('ir.model.fields', field_ids)]:
            cr.execute('SELECT module,name FROM ir_model_data WHERE model=%s AND res_id=ANY(%s) AND module<>%s',
                       (resource, ids, MODULE))
            for mod, name in cr.fetchall():
                adopt(cr, mod + '.' + name, 'legacy_ref_' + mod + '_' + name)
        alias(cr, 'model_' + table_name(new), 'ir.model', model_id)
        for (original_model, original_name), field in catalog.items():
            if original_model == old:
                new_name = FIELDS[old].get(original_name, original_name)
                alias(cr, 'field_' + table_name(new) + '__' + new_name, 'ir.model.fields', field['id'])
        # Retire old layouts in the same transaction. Native versioned views
        # replace their actions after module loading; no archived data is lost.
        cr.execute('UPDATE ir_ui_view SET active=FALSE WHERE model=%s', (old,))
        cr.execute('UPDATE base_automation SET active=FALSE WHERE model_id=%s', (model_id,))
        for table, column in references:
            cr.execute(sql.SQL('UPDATE {} SET {}=%s WHERE {}=%s').format(
                sql.Identifier(table), sql.Identifier(column), sql.Identifier(column)), (new, old))
        cr.execute("UPDATE ir_model SET state='base' WHERE id=%s", (model_id,))
        cr.execute("UPDATE ir_model_fields SET state='base' WHERE model=%s", (new,))
        cr.execute('UPDATE ir_model_fields SET relation=%s WHERE relation=%s', (new, old))
        cr.execute('SELECT id,domain,context FROM ir_act_window WHERE res_model=%s', (new,))
        for ident, domain, context in cr.fetchall():
            cr.execute('UPDATE ir_act_window SET domain=%s,context=%s WHERE id=%s',
                       (expression(old, domain), expression(old, context), ident))
        cr.execute('SELECT id,domain_force FROM ir_rule WHERE model_id=%s', (model_id,))
        for ident, domain in cr.fetchall():
            cr.execute('UPDATE ir_rule SET domain_force=%s WHERE id=%s', (expression(old, domain), ident))
        cr.execute('SELECT id,domain,context FROM ir_filters WHERE model_id IN (%s,%s)', (old, new))
        for ident, domain, context in cr.fetchall():
            cr.execute('UPDATE ir_filters SET model_id=%s,domain=%s,context=%s WHERE id=%s',
                       (new, expression(old, domain), expression(old, context), ident))
    for category in ('access', 'rules'):
        for old, new in ADOPTIONS[category].items():
            if not reference(cr, old) and not reference(cr, MODULE + '.' + new):
                # Source-specific Studio grants may never have existed here.
                # Native CSV grants are versioned and the original BPA grants
                # must still be present/adopted when their module is installed.
                assert not old.startswith('step_bpa_irrigation.'), ('Missing BPA grant', old)
                continue
            adopt(cr, old, new)
    for code in SCHEMA.SEQUENCES.values():
        cr.execute('SELECT id FROM ir_sequence WHERE code=%s', (code,))
        sequences = [r[0] for r in cr.fetchall()]
        if not sequences:
            continue  # post_init supplies only missing, fresh native sequences.
        cr.execute("SELECT module,name FROM ir_model_data WHERE model='ir.sequence' AND res_id=ANY(%s) AND module<>%s",
                   (sequences, MODULE))
        for mod, name in cr.fetchall():
            adopt(cr, mod + '.' + name, 'sequence_ref_' + mod + '_' + name)
    rename_reference_values(cr)
    # Rename only inherited fields that actually belong to these documents.
    # Unrelated Studio layouts are not broadly rewritten or deactivated.
    rewrite_foreign_views(cr, catalog)
    for old in before:
        cr.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table_name(MODELS[old]))))
        assert cr.fetchone()[0] == before[old], ('Row preservation failed', old)
    unified = prepare_tag_states(cr)
    return {'renamed': before, 'models': len(MODELS), 'transactional': True,
            'canonical_tag_states': unified}


def unify_tag_rows(cr, ids=None):
    """Use approved codes and the harvest center's company, never name matches."""
    cr.execute('SELECT id,code,company_id FROM step_packing_tag_state')
    candidates = {}
    for ident, code, company in cr.fetchall():
        candidates.setdefault(code, []).append((ident, company))
    cr.execute('SELECT t.id,s.code,a.company_id FROM step_agriculture_harvest_tag t '
               'JOIN step_agriculture_harvest_tag_state s ON s.id=t.tag_state_id '
               'LEFT JOIN step_agriculture_harvest_record h ON h.id=t.harvest_id '
               'LEFT JOIN account_analytic_account a ON a.id=h.cost_center_id '
               'WHERE (%s IS NULL OR t.id=ANY(%s))', (ids, ids))
    rows = cr.fetchall()
    for tag, original, company in rows:
        assert original in SCHEMA.TAG_STATE_POLICY, ('Unapproved original tag-state code', original)
        choices = [item for code in SCHEMA.TAG_STATE_CODES[SCHEMA.TAG_STATE_POLICY[original]]
                   for item in candidates.get(code, [])]
        scoped = [ident for ident, owner in choices if company and owner == company]
        scoped = scoped or [ident for ident, owner in choices if owner is None]
        assert len(scoped) == 1, ('Missing or ambiguous canonical tag state for company', original, company)
        cr.execute('UPDATE step_agriculture_harvest_tag SET packing_tag_state_id=%s WHERE id=%s',
                   (scoped[0], tag))
    return len(rows)


def prepare_tag_states(cr):
    # A new FK is the operational state. The original FK and master remain
    # untouched as immutable history, so preservation compares the same IDs.
    table = 'step_agriculture_harvest_tag'
    if not exists(cr, table):
        return {'mapped': 0, 'fresh_native_model': True}
    if column_exists(cr, table, 'packing_tag_state_id'):
        return {'already_unified': True}
    cr.execute('ALTER TABLE step_agriculture_harvest_tag ADD COLUMN packing_tag_state_id '
               'INTEGER REFERENCES step_packing_tag_state(id) ON DELETE RESTRICT')
    count = unify_tag_rows(cr)
    cr.execute('UPDATE ir_model_access SET perm_write=FALSE,perm_create=FALSE,perm_unlink=FALSE '
               "WHERE model_id=(SELECT id FROM ir_model WHERE model='step.agriculture.harvest.tag.state')")
    return {'mapped': count, 'policy': SCHEMA.TAG_STATE_POLICY}


def preserve_existing_access(cr):
    """Record this destination's grants, not another client's Studio grants."""
    plan = {}
    for old, new in MODELS.items():
        cr.execute('SELECT id FROM ir_model WHERE model IN (%s,%s)', (old, new))
        row = cr.fetchone()
        if not row:
            continue
        cr.execute('SELECT id,group_id,perm_read,perm_write,perm_create,perm_unlink,active '
                   'FROM ir_model_access WHERE model_id=%s', (row[0],))
        plan[new] = cr.fetchall()
    cr.execute("INSERT INTO ir_config_parameter(key,value) VALUES(%s,%s) "
               'ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value',
               (MODULE + '.migration_access', json.dumps(plan)))


def restore_existing_access(cr):
    cr.execute('SELECT value FROM ir_config_parameter WHERE key=%s', (MODULE + '.migration_access',))
    row = cr.fetchone()
    if not row:
        return
    for model, grants in json.loads(row[0]).items():
        ids = [grant[0] for grant in grants]
        cr.execute('UPDATE ir_model_access SET active=FALSE WHERE model_id='
                   '(SELECT id FROM ir_model WHERE model=%s) AND NOT (id=ANY(%s::int[]))', (model, ids))
        for ident, group, read, write, create, unlink, active in grants:
            if model == 'step.agriculture.harvest.tag.state':
                write = create = unlink = False
            cr.execute('UPDATE ir_model_access SET group_id=%s,perm_read=%s,perm_write=%s,'
                       'perm_create=%s,perm_unlink=%s,active=%s WHERE id=%s',
                       (group, read, write, create, unlink, active, ident))


def rename_reference_values(cr):
    cr.execute("SELECT model,name FROM ir_model_fields WHERE ttype='reference' AND store=TRUE")
    fields = [(table_name(model), name) for model, name in cr.fetchall()]
    if exists(cr, 'ir_property'):
        fields.append(('ir_property', 'value_reference'))
        fields.append(('ir_property', 'res_id'))
    for table, column in fields:
        if not exists(cr, table) or not column_exists(cr, table, column):
            continue
        for old, new in MODELS.items():
            cr.execute(sql.SQL('UPDATE {} SET {}=%s || substring({} from %s) WHERE {} LIKE %s').format(
                sql.Identifier(table), sql.Identifier(column), sql.Identifier(column), sql.Identifier(column)),
                (new, len(old) + 1, old + ',%'))


def rewrite_foreign_views(cr, catalog):
    from lxml import etree
    for model, mapping in SCHEMA.FOREIGN_FIELDS.items():
        cr.execute('SELECT id,arch_db FROM ir_ui_view WHERE model=%s', (model,))
        for ident, translated in cr.fetchall():
            result = {}
            for language, arch in (translated or {}).items():
                root = etree.fromstring(arch)
                if model == 'account.analytic.account':
                    for xpath in list(root):
                        # Only the legacy smart-button insertion is retired.
                        if xpath.tag == 'xpath' and xpath.xpath('.//button/field[starts-with(@name,"x_")]'):
                            root.remove(xpath)
                for field in root.xpath('.//field'):
                    related = catalog.get((model, field.get('name')), {}).get('relation')
                    if related in MODELS:
                        for attr in ('options', 'context'):
                            if field.get(attr):
                                field.set(attr, expression(related, field.get(attr)))
                text = etree.tostring(root, encoding='unicode')
                result[language] = SCHEMA.replace_tokens(text, mapping)
            cr.execute('UPDATE ir_ui_view SET arch_db=%s::jsonb WHERE id=%s', (json.dumps(result), ident))


def finalize(cr):
    restore_existing_access(cr)
    # Every original menu/action now resolves to versioned native views,
    # including direct bookmarks and old chart/report actions.
    for old, model in MODELS.items():
        suffix = model.removeprefix('step.agriculture.').replace('.', '_')
        views = {kind: reference(cr, MODULE + '.view_' + suffix + '_' + kind)[1]
                 for kind in ('list', 'form', 'search', 'graph', 'pivot')}
        cr.execute('SELECT id,view_mode FROM ir_act_window WHERE res_model=%s', (model,))
        for action, mode in cr.fetchall():
            modes = [kind for kind in (mode or 'list,form').split(',') if kind in views and kind != 'search']
            if not modes:
                modes = ['list', 'form']
            cr.execute('DELETE FROM ir_act_window_view WHERE act_window_id=%s', (action,))
            for sequence, kind in enumerate(modes):
                cr.execute('INSERT INTO ir_act_window_view(sequence,view_mode,view_id,act_window_id) VALUES(%s,%s,%s,%s)',
                           (sequence, kind, views[kind], action))
            cr.execute('UPDATE ir_act_window SET view_id=%s,search_view_id=%s,view_mode=%s WHERE id=%s',
                       (views[modes[0]], views['search'], ','.join(modes), action))
    return {'native_action_views': True, 'original_tag_states_preserved': True}


def snapshot(cr, baseline=None):
    """Compare all old columns and identities across table/field renames.

    New columns are excluded only through the explicit initial column inventory.
    Chatter and attachments are compared with normalized model references.
    """
    table_models = {table_name(old): old for old in MODELS}
    foreign_models = {table_name(name): name for name in SCHEMA.FOREIGN_FIELDS}
    if baseline is None:
        cr.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND "
                   "(tablename LIKE 'step_%' OR tablename LIKE 'x_%' OR tablename LIKE 'account_%' "
                   "OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename LIKE 'hr_%' "
                   "OR tablename IN ('res_partner','res_company','mail_message','mail_followers',"
                   "'mail_activity','ir_attachment','rating_rating','ir_property')) ORDER BY tablename")
        tables = {row[0] for row in cr.fetchall()}
        cr.execute("SELECT DISTINCT c.conrelid::regclass::text FROM pg_constraint c WHERE c.contype='f' "
                   "AND c.confrelid::regclass::text=ANY(%s)",
                   ([table_name(model) for model in [*MODELS, *MODELS.values()]],))
        tables.update(row[0] for row in cr.fetchall())
        baseline = {}
        reverse = {table_name(new): table_name(old) for old, new in MODELS.items()}
        for table in sorted(tables):
            logical = reverse.get(table, table)
            cr.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,))
            mapping = FIELDS.get(table_models.get(logical, foreign_models.get(logical, '')), {})
            inverse = {v: k for k, v in mapping.items()} if table != logical else {}
            baseline[logical] = {'columns': [inverse.get(row[0], row[0]) for row in cr.fetchall()]}
    output = {}
    for logical, original in baseline.items():
        assert re.fullmatch('[a-z_][a-z0-9_]*', logical)
        model = table_models.get(logical, foreign_models.get(logical, ''))
        native = table_name(MODELS[model]) if model in MODELS else logical
        table = native if exists(cr, native) else logical
        assert exists(cr, table), ('Lost historical table', logical)
        cr.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (table,))
        available = {row[0] for row in cr.fetchall()}
        mapping = FIELDS.get(model, {})
        chunks = []
        pairs = []
        for column in original['columns']:
            current = column if column in available else mapping.get(column)
            assert current in available, ('Lost historical column', logical, column)
            value = sql.SQL('t.{}').format(sql.Identifier(current))
            if column in ('model', 'res_model', 'model_name', 'res_model_name', 'application_model'):
                cases = sql.SQL(' ').join(sql.SQL('WHEN {} THEN {}').format(sql.Literal(new), sql.Literal(old))
                                         for old, new in MODELS.items())
                value = sql.SQL('CASE {} {} ELSE {} END').format(value, cases, value)
            pairs += [sql.Literal(column), value]
            if len(pairs) >= 80:
                chunks.append(sql.SQL('jsonb_build_object({})').format(sql.SQL(',').join(pairs)))
                pairs = []
        if pairs:
            chunks.append(sql.SQL('jsonb_build_object({})').format(sql.SQL(',').join(pairs)))
        row = sql.SQL(' || ').join(chunks)
        model_column = {'mail_message': 'model', 'mail_followers': 'res_model',
                        'mail_activity': 'res_model', 'ir_attachment': 'res_model',
                        'rating_rating': 'res_model'}.get(logical)
        where = (sql.SQL('WHERE t.{}=ANY({})').format(sql.Identifier(model_column),
                    sql.Literal([*MODELS, *MODELS.values()])) if model_column else sql.SQL(''))
        cr.execute(sql.SQL("SELECT count(*), md5(COALESCE(string_agg(digest,',' ORDER BY digest),'')) FROM "
                           "(SELECT md5(({})::text) AS digest FROM {} t {}) rows").format(row, sql.Identifier(table), where))
        count, digest = cr.fetchone()
        output[logical] = {'columns': original['columns'], 'count': count, 'digest': digest}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'finalize', 'snapshot'))
    parser.add_argument('database')
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    assert re.fullmatch('[A-Za-z0-9_]+', args.database)
    # Private baseline/code are read before dropping to the local PostgreSQL
    # account. No database password is needed, read, logged or changed.
    baseline = json.loads(args.baseline.read_text(encoding='utf-8')) if args.baseline else None
    import os
    import pwd
    if os.geteuid() == 0:
        account = pwd.getpwnam('postgres')
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    import psycopg2
    with psycopg2.connect(dbname=args.database, user='postgres') as connection:
        with connection.cursor() as cr:
            if args.action == 'snapshot':
                result = snapshot(cr, baseline)
            else:
                result = prepare(cr) if args.action == 'prepare' else finalize(cr)
    if args.action == 'snapshot':
        print(json.dumps(result))
        return
    print('AGRICULTURE_MIGRATION_OK ' + json.dumps(result))


if __name__ == '__main__':
    main()
