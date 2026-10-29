"""T132–134: adopt known prototype fields in place, preserving IDs and values."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from psycopg2 import sql

MODULE = 'step_packing_ticket_revision'
DATE_POLICY = 'pending'
MAPPING = {
    'stock.picking': {'x_studio_planta_frigorfico': 'step_receiving_packing_id'},
    'step.packing.production': {'x_studio_packing': 'step_legacy_packing_partner_id',
                                'x_studio_fecha_proceso': 'step_legacy_process_date'},
    'step.packing.picking.tag.line': {'x_studio_kg_x_caja': 'step_legacy_kg_per_box'},
}


def columns(cr, table):
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [table])
    return {r[0] for r in cr.fetchall()}


def adopt(cr, model, ident, alias):
    cr.execute('SELECT module,name FROM ir_model_data WHERE model=%s AND res_id=%s AND module<>%s', [model, ident, MODULE])
    for index, (module, name) in enumerate(cr.fetchall()):
        cr.execute('UPDATE ir_model_data SET module=%s,name=%s,noupdate=TRUE WHERE module=%s AND name=%s',
                   [MODULE, 'legacy_%s_%s_%s' % (model.replace('.', '_'), ident, index), module, name])
    cr.execute('SELECT model,res_id FROM ir_model_data WHERE module=%s AND name=%s', [MODULE, alias])
    found = cr.fetchone()
    assert not found or found == (model, ident), ('Conflicting XML ID', alias)
    if not found:
        cr.execute('INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES(%s,%s,%s,%s,TRUE)', [MODULE, alias, model, ident])


def values(cr, table, field):
    cr.execute(sql.SQL('SELECT id,to_jsonb({}) FROM {} ORDER BY id').format(sql.Identifier(field), sql.Identifier(table)))
    return cr.fetchall()


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def prepare(cr, proof):
    production = 'step_packing_production'
    # Pending means preserve the current native date and the separate prototype
    # value. It never means approval to choose or overwrite either date.
    result = {'fields': [], 'views': [], 'date_policy': DATE_POLICY, 'previous_dates': [], 'pending_dates': []}
    if 'x_studio_fecha_proceso' in columns(cr, production) and DATE_POLICY == 'pending':
        cr.execute('SELECT id,to_jsonb(date),to_jsonb(x_studio_fecha_proceso) FROM step_packing_production WHERE x_studio_fecha_proceso IS NOT NULL AND x_studio_fecha_proceso IS DISTINCT FROM date ORDER BY id')
        result['pending_dates'] = cr.fetchall()
    # Retire only the two recognized layouts; keep their IDs and original arch.
    old_names = {name for fields in MAPPING.values() for name in fields}
    cr.execute("SELECT id,model,name,arch_db FROM ir_ui_view WHERE active AND model IN ('stock.picking','step.packing.production')")
    for ident, model, name, translations in cr.fetchall():
        text = json.dumps(translations)
        found = set(re.findall(r'x_studio_[a-zA-Z0-9_]+', text))
        if not found & old_names:
            continue
        assert name.startswith('Odoo Studio:') and found <= old_names, 'Mixed custom layout requires explicit migration'
        result['views'].append({'id': ident, 'arch': translations})
        adopt(cr, 'ir.ui.view', ident, 'legacy_view_%s' % ident)
        cr.execute('UPDATE ir_ui_view SET active=FALSE WHERE id=%s', [ident])
    for model, mapping in MAPPING.items():
        table = model.replace('.', '_')
        for old, new in mapping.items():
            cr.execute('SELECT id,ttype,relation FROM ir_model_fields WHERE model=%s AND name=%s', [model, old])
            field = cr.fetchone()
            if not field:
                continue
            actual = columns(cr, table)
            assert old in actual and new not in actual, ('Parallel field needs reconciliation', old, new)
            result['fields'].append({'model': model, 'id': field[0], 'name': new,
                                     'hash': fingerprint(values(cr, table, old))})
            cr.execute(sql.SQL('ALTER TABLE {} RENAME COLUMN {} TO {}').format(sql.Identifier(table), sql.Identifier(old), sql.Identifier(new)))
            cr.execute("UPDATE ir_model_fields SET name=%s,state='base' WHERE id=%s", [new, field[0]])
            adopt(cr, 'ir.model.fields', field[0], 'field_%s__%s' % (table, new))
    actual = columns(cr, production)
    if 'step_legacy_packing_partner_id' in actual:
        cr.execute('SELECT count(*) FROM step_packing_production WHERE step_legacy_packing_partner_id IS NOT NULL AND packing_partner_id IS NOT NULL AND step_legacy_packing_partner_id<>packing_partner_id')
        assert cr.fetchone()[0] == 0, 'Conflicting native/prototype Packing requires review'
        cr.execute('UPDATE step_packing_production SET packing_partner_id=step_legacy_packing_partner_id WHERE packing_partner_id IS NULL AND step_legacy_packing_partner_id IS NOT NULL')
    if DATE_POLICY == 'prototype' and 'step_legacy_process_date' in actual:
        cr.execute('SELECT id,to_jsonb(date) FROM step_packing_production WHERE step_legacy_process_date IS NOT NULL AND step_legacy_process_date IS DISTINCT FROM date ORDER BY id')
        result['previous_dates'] = cr.fetchall()
        cr.execute('ALTER TABLE step_packing_production ADD COLUMN IF NOT EXISTS step_previous_process_date date')
        cr.execute('UPDATE step_packing_production SET step_previous_process_date=date,date=step_legacy_process_date WHERE step_legacy_process_date IS NOT NULL AND step_legacy_process_date IS DISTINCT FROM date')
    # Saved filters, field dependencies and custom server expressions follow the
    # renamed field IDs/names. Original archived view XML intentionally stays intact.
    for model, mapping in MAPPING.items():
        for table, column, scope, params in [
            ('ir_filters', 'domain', 'model_id=%s', [model]),
            ('ir_filters', 'context', 'model_id=%s', [model]),
            ('ir_model_fields', 'related', 'model=%s', [model]),
            ('ir_model_fields', 'depends', 'model=%s', [model]),
        ]:
            for old, new in mapping.items():
                cr.execute(sql.SQL('UPDATE {} SET {}=replace({},%s,%s) WHERE '+scope+' AND {} LIKE %s').format(
                    sql.Identifier(table), sql.Identifier(column), sql.Identifier(column), sql.Identifier(column)),
                    [old, new, *params, '%' + old + '%'])
    proof.write_text(json.dumps(result, ensure_ascii=False, indent=2))


def finalize(cr, proof):
    source = json.loads(proof.read_text())
    for field in source['fields']:
        cr.execute('SELECT name,state FROM ir_model_fields WHERE id=%s', [field['id']])
        assert cr.fetchone() == (field['name'], 'base'), 'Original field identity lost'
        assert fingerprint(values(cr, field['model'].replace('.', '_'), field['name'])) == field['hash'], 'Original prototype values changed'
    for view in source['views']:
        cr.execute('SELECT active,arch_db FROM ir_ui_view WHERE id=%s', [view['id']])
        active, arch = cr.fetchone()
        assert not active and arch == view['arch'], 'Original prototype layout must remain archived'
    for ident, old_date in source['previous_dates']:
        cr.execute('SELECT to_jsonb(step_previous_process_date) FROM step_packing_production WHERE id=%s', [ident])
        assert cr.fetchone()[0] == old_date, 'Previous native process date lost'
    for ident, native, prototype in source['pending_dates']:
        cr.execute('SELECT to_jsonb(date),to_jsonb(step_legacy_process_date) FROM step_packing_production WHERE id=%s', [ident])
        assert cr.fetchone() == (native, prototype), 'Pending date decision must preserve both values'


def snapshot_row(table, original_columns, current_columns):
    """Normalize only approved renames/copies; all other business bytes stay checked."""
    row = 'to_jsonb(t)'
    # Model names contain underscores too; resolve explicitly.
    mapping = next((v for k, v in MAPPING.items() if k.replace('.', '_') == table), {})
    permitted = set(original_columns)
    for old, new in mapping.items():
        if old in permitted:
            permitted.remove(old)
            permitted.add(new)
        row = "CASE WHEN %s ? '%s' THEN (%s-'%s')||jsonb_build_object('%s',%s->'%s') ELSE %s END" % (row, old, row, old, new, row, old, row)
    additions = sorted(set(current_columns) - permitted)
    if additions:
        row = "(%s-ARRAY[%s])" % (row, ','.join("'%s'" % name for name in additions))
    if table == 'step_packing_production':
        # This copy only fills an empty native field; conflicting values stop.
        row = "jsonb_set(%s,'{packing_partner_id}',COALESCE(NULLIF(%s->'packing_partner_id','null'::jsonb),%s->'step_legacy_packing_partner_id','null'::jsonb))" % (row, row, row)
        if DATE_POLICY == 'prototype':
            row = "jsonb_set(%s,'{date}',COALESCE(NULLIF(%s->'step_legacy_process_date','null'::jsonb),%s->'date','null'::jsonb))" % (row, row, row)
    return row


def main():
    import psycopg2
    p = argparse.ArgumentParser(); p.add_argument('action', choices=('prepare', 'finalize'))
    p.add_argument('database'); p.add_argument('proof', type=Path); args = p.parse_args()
    assert args.database.startswith('MANAGEMENT_QA_') or args.database in ('LAB_TAREAS', 'CERRO_EL_PLOMO', 'QA-CERROELPLOMO')
    with psycopg2.connect(dbname=args.database, user='postgres') as connection:
        with connection.cursor() as cr:
            globals()[args.action](cr, args.proof)
    print('PACKING_TICKET_SCHEMA_' + args.action.upper() + '_OK')


if __name__ == '__main__':
    main()
