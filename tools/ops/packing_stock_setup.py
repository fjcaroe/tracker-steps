"""T121: allow only new native warehouse configuration, preserving all old rows."""
import json
import subprocess

CONFIG_TABLES = ('stock_warehouse', 'stock_location', 'stock_picking_type', 'stock_rule', 'stock_route')


def capture(query, database):
    return {table: int(query(database, 'SELECT COALESCE(max(id),0) FROM ' + table)) for table in CONFIG_TABLES}


def capture_inactive_types(query, database):
    return json.loads(query(database, "SELECT COALESCE(json_object_agg(id,company_id),'{}'::json) FROM stock_picking_type WHERE code='internal' AND active=false"))


def snapshot_filter(table, row, limits, inactive_types):
    if table == 'res_company':
        row = "(%s-ARRAY['write_date','write_uid'])" % row
    if table == 'res_partner':
        # Module recomputations and native warehouse partner setup touch audit
        # metadata. Every prior business field and every partner ID still hashes.
        row = "(%s-ARRAY['write_date','write_uid'])" % row
    if table == 'stock_picking_type' and inactive_types:
        ids = ','.join(str(int(key)) for key in inactive_types)
        # A second warehouse enables existing internal operation types. Only
        # previously inactive types qualify; deactivations of active ones fail.
        row = "CASE WHEN t.id IN (%s) THEN (jsonb_set(%s,'{active}','false'::jsonb)-ARRAY['write_date','write_uid']) ELSE %s END" % (ids,row,row)
    if table in limits:
        return row, ' WHERE id <= %s' % limits[table]
    if table == 'stock_route_warehouse':
        return row, ' WHERE warehouse_id <= %s' % limits['stock_warehouse']
    return row, ''


def configure(base, options, database, source, opts, stage, query, limits, inactive_types):
    # native_business_profile is copied alongside the publisher, not into addons.
    from pathlib import Path
    script = "import sys\nsys.path.insert(0,%r)\n" % str(Path(__file__).resolve().parent)
    script += """
import json
from native_business_profile import scoped_business_environment
company=scoped_business_environment(env).company
warehouse=company._configure_packing_warehouse()
assert warehouse.company_id==company
assert company.step_packing_material_location_id.usage=='internal'
assert company.step_packing_fruit_location_id.usage=='internal'
env.cr.commit()
print('PACKING_STOCK_CONFIGURED '+json.dumps({'company':company.id,'warehouse':warehouse.id,
    'material_location':company.step_packing_material_location_id.id,
    'fruit_location':company.step_packing_fruit_location_id.id}))
"""
    data = ['--data-dir=' + str(stage/'data')] if database.startswith('MANAGEMENT_QA_') else []
    result = subprocess.run(base + ['shell'] + options + data + ['-d', database,
        '--addons-path=' + str(source) + ',' + opts['addons_path'], '--log-level=error'],
        input=script, text=True, capture_output=True)
    (stage/('packing-config-'+database+'.log')).write_text(result.stdout+result.stderr)
    assert result.returncode == 0 and 'PACKING_STOCK_CONFIGURED ' in result.stdout, result.stderr[-3000:]
    line = next(line for line in result.stdout.splitlines() if line.startswith('PACKING_STOCK_CONFIGURED '))
    config = json.loads(line.split(' ',1)[1])
    # All additions are logistics configuration of the explicitly selected company.
    for table, maximum in limits.items():
        assert query(database, 'SELECT count(*) FROM %s WHERE id>%s AND company_id IS DISTINCT FROM %s' %
                     (table, maximum, config['company'])) == '0', 'Unexpected warehouse configuration company: '+table
    foreign = [str(int(key)) for key, company in inactive_types.items() if company != config['company']]
    if foreign:
        assert query(database, "SELECT count(*) FROM stock_picking_type WHERE id IN (%s) AND active=true" % ','.join(foreign)) == '0', 'Internal operations of another company were activated'
    print(line, flush=True)
