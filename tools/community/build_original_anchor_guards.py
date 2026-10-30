"""Generate private, fail-closed anti-unlink SQL for one anchored sandbox.

This file never connects to PostgreSQL or loads Odoo. The coordinator must
capture the anchor BEFORE staging, validate complete source witnesses, inspect
the generated SQL and execute it in the new private clone under the lease.
These guards are diagnostic constraints, not a provider/adoption implementation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

import payroll_configuration_adoption_preflight as gate
from plan_original_payroll_bootstrap import original_aliases, source_report


IDENTITY_TABLES = {
    'ir_model_data': ('id', 'module', 'name', 'model', 'res_id', 'noupdate'),
    'ir_model': ('id', 'model', 'state'),
    'ir_model_fields': ('id', 'model', 'name', 'state'),
    'ir_model_fields_selection': ('id', 'field_id', 'value'),
}


def _ids(rows):
    ids = [row['id'] for row in rows]
    gate.require(ids and all(type(value) is int and value > 0 for value in ids)
        and len(ids) == len(set(ids)), 'invalid-anchor-primary-keys')
    return sorted(ids)


def guard_specs(capsule, original_identity, anchor_identity, preflight):
    aliases = original_aliases(capsule, original_identity)
    actual = {key(row): row for row in anchor_identity['original_xmlids']}
    for row in aliases:
        gate.require(actual.get(key(row)) == row, 'anchor-original-alias-identity-drift')
    report = source_report(preflight, original_identity)
    gate.require(actual.get(('hr_payroll', 'action_report_payslip')) == report['original_alias'],
                 'anchor-original-report-alias-drift')
    models = [row for row in anchor_identity['ir_model']
              if row['id'] == report['binding_model_id'] or row['model'] == 'hr.payslip']
    gate.require(len(models) == 1 and models[0]['id'] == report['binding_model_id']
        and models[0]['model'] == 'hr.payslip', 'anchor-original-binding-model-drift')
    specs = []
    for table, columns in IDENTITY_TABLES.items():
        rows = anchor_identity['original_xmlids' if table == 'ir_model_data' else table]
        gate.require(all(set(columns) <= row.keys() for row in rows), 'incomplete-anchor-metadata')
        specs.append({'table': table, 'key': 'id', 'ids': _ids(rows), 'columns': list(columns),
                      'scope': 'original-anchor-metadata-identity'})
    # Protect only the original physical columns. A genuinely new nullable OCA
    # column is not a license to alter any captured original value or audit.
    for table, rows in gate.capsule_rows(capsule).items():
        columns = set(rows[0])
        gate.require(all(set(row) == columns for row in rows), 'inconsistent-source-row-columns')
        specs.append({'table': table, 'key': 'id', 'ids': _ids(rows), 'columns': sorted(columns),
                      'scope': 'all-original-master-column-values'})
    report_columns = sorted(row['column_name'] for row in preflight['source_metadata']['columns']
                            if row['table_name'] == 'ir_act_report_xml')
    gate.require(len(set(report_columns)) == len(report_columns)
        and {'id', 'type', 'name', 'model', 'report_type', 'report_name', 'binding_model_id',
             'attachment', 'attachment_use'} <= set(report_columns), 'original-report-all-column-catalog-required')
    specs.append({'table': 'ir_act_report_xml', 'key': 'id', 'ids': [462],
        'columns': report_columns, 'scope': 'all-original-report-columns'})
    specs.append({'table': 'res_groups_report_rel', 'key': 'uid', 'ids': [462],
        'columns': ['uid', 'gid'], 'scope': 'original-report-role-pairs'})
    return specs


def key(row):
    return row['module'], row['name']


def render_sql(database, specs):
    gate.require(re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_[A-Za-z0-9_]+', database),
                 'new-private-native-anchor-required')
    statements = ['BEGIN;', "DO $anchor$ BEGIN IF current_database() <> " + gate.literal(database)
        + " THEN RAISE EXCEPTION 'Original anchor guard: wrong database'; END IF; "
        "IF EXISTS(SELECT 1 FROM ir_module_module WHERE state='to remove') THEN "
        "RAISE EXCEPTION 'Original anchor guard: uninstall state forbidden'; END IF; END $anchor$;"]
    tables = set()
    for spec in specs:
        table, column = spec['table'], spec['key']
        gate.require(table not in tables, 'duplicate-guard-table')
        tables.add(table)
        identifiers = [table, column] + spec['columns']
        gate.require(all(re.fullmatch(r'[a-z_][a-z0-9_]*', item) for item in identifiers), 'unsafe-guard-identifier')
        gate.require(len(set(spec['columns'])) == len(spec['columns']) and column in spec['columns'],
                     'invalid-guard-column-contract')
        gate.require(spec['ids'] and all(type(value) is int and value > 0 for value in spec['ids'])
            and len(set(spec['ids'])) == len(spec['ids']), 'invalid-guard-id-contract')
        qualified = 'public.' + gate.identifier(table)
        function = 'public.' + gate.identifier('step_anchor_guard_' + table)
        ids = 'ARRAY[' + ','.join(map(str, spec['ids'])) + ']::integer[]'
        columns = 'ARRAY[' + ','.join(map(gate.literal, spec['columns'])) + ']::text[]'
        # Assertion occurs in the same transaction as guard creation. Relation
        # tables have no unique row ID and can have zero original report roles.
        if column == 'id':
            statements.append("DO $anchor$ BEGIN IF (SELECT count(*) FROM " + qualified
                + ' WHERE ' + gate.identifier(column) + '=ANY(' + ids + ')) <> ' + str(len(spec['ids']))
                + " THEN RAISE EXCEPTION 'Original anchor guard: missing original rows in " + table
                + "'; END IF; END $anchor$;")
        statements.append('CREATE FUNCTION ' + function + '() RETURNS trigger LANGUAGE plpgsql AS $anchor$\n'
            "BEGIN\n IF TG_OP='TRUNCATE' THEN\n"
            "  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Original anchor guard: truncate " + table + "';\n END IF;\n"
            ' IF OLD.' + gate.identifier(column) + '=ANY(' + ids + ') THEN\n'
            "  IF TG_OP='DELETE' THEN\n"
            "   RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Original anchor guard: delete " + table + "';\n  END IF;\n"
            '  IF (SELECT jsonb_object_agg(k,to_jsonb(NEW)->k) FROM unnest(' + columns + ') k)\n'
            '   IS DISTINCT FROM (SELECT jsonb_object_agg(k,to_jsonb(OLD)->k) FROM unnest(' + columns + ') k) THEN\n'
            "   RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Original anchor guard: original value " + table + "';\n  END IF;\n END IF;\n"
            " IF TG_OP='DELETE' THEN RETURN OLD; END IF;\n RETURN NEW;\nEND\n$anchor$;")
        statements.append('CREATE TRIGGER step_anchor_preserve_original_row BEFORE DELETE OR UPDATE ON '
            + qualified + ' FOR EACH ROW EXECUTE FUNCTION ' + function + '();')
        statements.append('CREATE TRIGGER step_anchor_preserve_original_truncate BEFORE TRUNCATE ON '
            + qualified + ' FOR EACH STATEMENT EXECUTE FUNCTION ' + function + '();')
    statements.append('COMMIT;')
    return '\n\n'.join(statements) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capsule', 'identity-before', 'anchor-identity', 'source-preflight', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--expected-capsule-sha256', required=True)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    gate.require(args.output.resolve().is_relative_to(Path('/opt/steps-validation'))
        and not args.output.exists(), 'new-private-sql-artifact-required')
    gate.require(hashlib.sha256(args.capsule.read_bytes()).hexdigest() == args.expected_capsule_sha256,
                 'sealed-original-capsule-required')
    read = lambda path: json.loads(path.read_text())
    specs = guard_specs(read(args.capsule), read(args.identity_before), read(args.anchor_identity), read(args.source_preflight))
    sql = render_sql(args.database, specs)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        stream.write(sql)
    receipt = {'artifact': str(args.output), 'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
        'tables': len(specs), 'database_connection_opened': False, 'sql_executed': False,
        'original_metadata_or_data_rewritten': False,
        'ddl_drop_and_schema_changes_guarded': False, 'adoption_authorized': False,
        'postgresql_trigger_behavior_tested': False,
        'scope': [{'table': row['table'], 'primary_key_count': len(row['ids']),
                   'key': row['key'], 'columns': row['columns'], 'scope': row['scope']} for row in specs],
        'provenance': {name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for name, path in (('capsule', args.capsule), ('original_identity', args.identity_before),
                ('anchor_identity', args.anchor_identity), ('source_preflight', args.source_preflight),
                ('generator', Path(__file__)))}}
    receipt_path = args.output.with_name(args.output.name + '.receipt.json')
    with os.fdopen(os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({name: receipt[name] for name in ('artifact', 'sha256', 'tables',
        'database_connection_opened', 'sql_executed', 'adoption_authorized')}))


if __name__ == '__main__':
    main()
