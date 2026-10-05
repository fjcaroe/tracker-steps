"""Compare hashes/IDs before and after migrating a whitelisted disposable clone."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql

MODELS = ('step_export_estimate', 'step_export_estimate_line', 'step_export_estimate_week',
    'step_export_grower_rate', 'step_export_grower_discount', 'step_export_producer_settlement',
    'step_export_producer_settlement_line', 'step_export_producer_settlement_discount', 'step_producer_season_statement')
DATABASES = {label: 'AGRO_INTEGRATION_QA_20261005_' + label.upper() + '_PHASEB' for label in ('development', 'demo')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=DATABASES)
    parser.add_argument('mode', choices=('before', 'after'))
    args = parser.parse_args()
    connection = psycopg2.connect(dbname=DATABASES[args.environment])
    root = Path('/opt/steps-agro-qa') / args.environment / 'phaseb'
    snapshot_path = root / 'migration-before.json'
    snapshot = {'tables': {}, 'xmlids': {}}
    with connection, connection.cursor() as cr:
        for table in MODELS:
            cr.execute('SELECT to_regclass(%s)', [table])
            if not cr.fetchone()[0]:
                continue
            # New standalone dimensions must be backfilled; old amounts and IDs
            # must remain identical. Do not print or persist customer contents.
            cr.execute(sql.SQL("SELECT id,(to_jsonb(t)-ARRAY['write_date','date','season_id','species_id','description'])::text FROM {} t ORDER BY id").format(sql.Identifier(table)))
            rows = cr.fetchall()
            snapshot['tables'][table] = {'count': len(rows), 'sha256': hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
        tree = ast.parse((root / 'addons/step_producers/legacy_ids.py').read_text())
        ids = ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.Assign)))
        cr.execute("SELECT name,model,res_id FROM ir_model_data WHERE module='step_export' AND name=ANY(%s) ORDER BY name", [list(ids)])
        snapshot['xmlids'] = {row[0]: [row[1], row[2]] for row in cr.fetchall()}
        if args.mode == 'after':
            cr.execute('''SELECT COUNT(*) FROM step_export_producer_settlement p
                JOIN step_export_receiver_settlement r ON p.receiver_settlement_id=r.id
                WHERE p.date IS DISTINCT FROM r.date OR p.company_id IS DISTINCT FROM r.company_id
                   OR p.season_id IS DISTINCT FROM r.season_id OR p.species_id IS DISTINCT FROM r.species_id''')
            assert cr.fetchone()[0] == 0, 'Historical settlement dimensions were not preserved'
            for name, expected in snapshot['xmlids'].items():
                cr.execute("SELECT model,res_id FROM ir_model_data WHERE module='step_producers' AND name=%s", [name])
                assert list(cr.fetchone() or []) == expected, name
    if args.mode == 'before':
        snapshot_path.write_text(json.dumps(snapshot, sort_keys=True))
        os.chmod(snapshot_path, 0o600)
    else:
        assert snapshot == json.loads(snapshot_path.read_text()), 'Business hashes or original XML IDs changed'
    print('MIGRATION_PRESERVATION_' + args.mode.upper() + '_OK ' + json.dumps({
        'database': DATABASES[args.environment], 'table_counts': {name: value['count'] for name, value in snapshot['tables'].items()},
        'original_xmlids': len(snapshot['xmlids'])}))


if __name__ == '__main__':
    main()
