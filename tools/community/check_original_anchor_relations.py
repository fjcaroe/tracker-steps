"""Gate the physical relation additions of a private original-payroll handover."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from classify_original_anchor_preservation import constraint_catalog, require
from original_anchor_readonly_sql import ReadOnlyReviewSQL
from original_external_references import ident
from payroll_configuration_adoption_preflight import literal


def column_contract(sql, database, table, column):
    result = sql(database, (
        "SELECT coalesce(json_agg(json_build_object('table_name',c.relname,"
        "'column_name',a.attname,'not_null',a.attnotnull,"
        "'sql_type',format_type(a.atttypid,a.atttypmod),"
        "'default_md5',md5(pg_get_expr(d.adbin,d.adrelid)))),'[]'::json) "
        "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
        "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
        "WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped "
        "AND c.relname=" + literal(table) + " AND a.attname=" + literal(column)
    ))
    rows = json.loads(result)
    require(len(rows) <= 1, 'ambiguous-public-column')
    return rows[0] if rows else None


def column_counts(sql, database, table, column):
    query = (
        "SELECT json_build_object('rows',count(*),'populated',count(" + ident(column)
        + ")) FROM public." + ident(table)
    )
    return json.loads(sql(database, query))


def added_relation(sql, source, target, expected, actual, new_columns):
    table = actual['table_name']
    require(actual['kind'] == 'f' and actual['valid'] and not actual['deferrable']
        and not actual['deferred'] and actual['match'] == 's' and actual['on_update'] == 'a'
        and actual['on_delete'] in ('n', 'r'), 'unreviewed-foreign-key-policy')
    require(actual['referenced_schema'] == 'public' and actual['referenced_columns'] == ['id']
        and len(actual['columns']) == 1, 'unreviewed-foreign-key-endpoints')
    require(hashlib.md5(actual['definition'].encode()).hexdigest() == expected['definition_md5'],
        'foreign-key-definition-drifted')
    column = actual['columns'][0]
    require(column in new_columns.get(table, ()) and column_contract(sql, source, table, column) is None,
        'foreign-key-touches-original-column')
    target_column = column_contract(sql, target, table, column)
    require(target_column is not None and target_column['sql_type'] == 'integer',
        'foreign-key-storage-drifted')
    counts = column_counts(sql, target, table, column)
    return {
        'table': table, 'column': column, 'name': actual['name'],
        'references': actual['referenced_table'], 'on_delete': actual['on_delete'],
        'nullable': not target_column['not_null'], **counts,
        'admission': 'empty-addition' if counts['populated'] == 0 else 'requires-population-proof',
    }


def required_column(sql, source, target, change):
    before, after = change['before'], change['after']
    table, column = before['table_name'], before['column_name']
    require(before['not_null'] and after == {**before, 'not_null': False},
        'unreviewed-original-column-change')
    require(column_contract(sql, source, table, column) == before
        and column_contract(sql, target, table, column) == after, 'original-column-contract-drifted')
    counts = column_counts(sql, target, table, column)
    return {
        'table': table, 'column': column, 'rows': counts['rows'],
        'nulls': counts['rows'] - counts['populated'], 'not_null_restored': False,
    }


def inspect(sql, source, target, review):
    require(review['database'] == target and review['read_only'] is True
        and review['acceptance_authorized_by_this_review'] is False, 'exact-anchor-review-required')
    require(review['postgresql_readonly_execution']['databases'] == [target, source],
        'anchor-review-pair-mismatch')
    differences = review['original_physical_schema_differences_requiring_review']
    require(not differences['constraints'], 'original-constraint-changes-require-separate-proof')
    expected = {(row['table_name'], row['name']): row
        for row in review['added_constraints_requiring_review']}
    require(expected and len(expected) == len(review['added_constraints_requiring_review']),
        'empty-or-duplicate-added-constraint-review')
    require(not constraint_catalog(sql, source, expected), 'candidate-constraint-already-exists-in-source')
    actual = {(row['table_name'], row['name']): row for row in constraint_catalog(sql, target, expected)}
    require(actual.keys() == expected.keys(), 'reviewed-constraint-missing-from-target')
    relations = [added_relation(sql, source, target, expected[key], actual[key], review['new_columns'])
        for key in sorted(expected)]
    required_columns = [required_column(sql, source, target, change) for change in differences['columns']]
    return {
        'schema': 1, 'foreign_keys': relations, 'original_required_columns': required_columns,
        'all_reviewed_foreign_keys_empty_additions': all(row['populated'] == 0 for row in relations),
        'original_required_schema_restored': not required_columns,
        'financial_certified': False, 'integral_conversion': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('stage', 'review', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    stage = args.stage.resolve()
    require(stage.is_relative_to('/opt/steps-validation') and args.review.resolve().parent == stage
        and args.output.resolve().parent == stage, 'private-stage-and-receipt-required')
    plan = json.loads((stage / 'handover-plan.json').read_bytes())
    target, source = plan['database'], plan['reference_database']
    executor = ReadOnlyReviewSQL(target, source)
    review_bytes = args.review.read_bytes()
    result = inspect(executor, source, target, json.loads(review_bytes))
    result.update(review_sha256=hashlib.sha256(review_bytes).hexdigest(),
        tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        postgresql_readonly_execution=executor.proof())
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(result, stream, indent=2)
    require(result['all_reviewed_foreign_keys_empty_additions'],
        'populated-new-relation-requires-its-own-proof')


if __name__ == '__main__':
    main()
