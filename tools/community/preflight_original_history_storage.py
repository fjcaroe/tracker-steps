"""Read-only gate BEFORE the first Odoo initialization of private payroll DBs.

Only catalog metadata, row counts and company/name NULL counts are selected.
No ORM, initializer, payroll value, default materialization or conversion.
The SQL callback belongs to the coordinator and must execute the supplied SQL
verbatim using its trusted read-only wrapper; this helper supplies no secrets.
"""
import hashlib
import json
import re


MODES = ('cold-community', 'anchored', 'native')
TABLES = {'hr_payslip': ('company_id', 'int4', 'integer'),
    'hr_payslip_line': ('name', 'varchar', 'character varying')}


def require(value, code):
    if not value:
        raise ValueError('original-history-storage-' + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def authorize(database, mode):
    require(mode in MODES and isinstance(database, str), 'explicit-private-mode-required')
    prefix = {'cold-community': r'COMMUNITY_PAYROLL_API_',
        'anchored': r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_',
        'native': r'MANAGEMENT_QA_CERRO_PAYROLL_API_'}[mode]
    require(re.fullmatch(prefix + r'[A-Za-z0-9_]+', database)
        and (mode != 'native' or '_ORIGINAL_HANDOVER_' not in database), 'private-database-prefix-required')


def _table_expression(table):
    # Both names are fixed in this versioned module, never caller SQL input.
    column = TABLES[table][0]
    return """(SELECT json_build_object('schema',n.nspname,'table',c.relname,'kind',c.relkind,
 'oid',c.oid::bigint,'columns',(SELECT coalesce(json_agg(json_build_object(
   'name',a.attname,'sql_type',format_type(a.atttypid,a.atttypmod),'type_name',t.typname,
   'type_oid',a.atttypid::bigint,'type_modifier',a.atttypmod,'not_null',a.attnotnull,
   'has_default',a.atthasdef,'identity',a.attidentity,'generated',a.attgenerated) ORDER BY a.attnum),'[]'::json)
   FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid
   WHERE a.attrelid=c.oid AND a.attname='%s' AND a.attnum>0 AND NOT a.attisdropped))
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE c.oid=to_regclass('public.%s'))""" % (column, table)


METADATA_EXPRESSION = 'json_build_object(' + ','.join("'%s',%s" % (table, _table_expression(table)) for table in TABLES) + ')'
HEADER = """BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT json_build_object('database',current_database(),
 'transaction_read_only',current_setting('transaction_read_only'),
 'transaction_isolation',current_setting('transaction_isolation'),
 'primary',NOT pg_is_in_recovery(),'metadata',"""
DISCOVERY_QUERY = HEADER + METADATA_EXPRESSION + ');\nROLLBACK;'


def validate_metadata(snapshot, database, mode):
    authorize(database, mode)
    require(snapshot.get('database') == database and snapshot.get('transaction_read_only') == 'on'
        and snapshot.get('transaction_isolation') == 'repeatable read' and snapshot.get('primary') is True,
        'actual-primary-repeatable-read-readonly-required')
    metadata = snapshot.get('metadata')
    require(isinstance(metadata, dict) and set(metadata) == set(TABLES), 'exact-two-history-catalog-entries-required')
    for table, (field, pg_name, sql_type) in TABLES.items():
        entry = metadata[table]
        if entry is None:
            require(mode == 'cold-community', 'original-history-table-missing:' + table)
            continue
        require(entry.get('schema') == 'public' and entry.get('table') == table and entry.get('kind') == 'r'
            and type(entry.get('oid')) is int and entry['oid'] > 0,
            'real-original-history-table-required:' + table)
        columns = entry.get('columns')
        require(isinstance(columns, list) and len(columns) == 1, 'history-column-missing-or-ambiguous:' + table)
        column = columns[0]
        require(column.get('name') == field and column.get('type_name') == pg_name
            and column.get('sql_type') == sql_type and column.get('type_oid') == (23 if pg_name == 'int4' else 1043)
            and column.get('type_modifier') == -1 and type(column.get('not_null')) is bool
            and type(column.get('has_default')) is bool and column.get('identity') == '' and column.get('generated') == '',
            'original-column-type-or-generated-storage-differs:' + table)
        require(table != 'hr_payslip_line' or column['not_null'] is True, 'line-name-original-not-null-required')
        require(table != 'hr_payslip' or mode == 'cold-community' or column['not_null'] is True,
            'original-company-not-null-required')
    return metadata


def capture_query(metadata):
    require(isinstance(metadata, dict) and set(metadata) == set(TABLES), 'discovered-fixed-history-tables-required')
    expressions = []
    for table, (column, pg_name, sql_type) in TABLES.items():
        if metadata[table] is None:
            expression = 'NULL'
        else:
            expression = "(SELECT json_build_object('rows',count(*),'null_rows',count(*) FILTER (WHERE %s IS NULL)) FROM public.%s)" % (column, table)
        expressions.append("'%s',%s" % (table, expression))
    return HEADER + METADATA_EXPRESSION + ", 'null_counts',json_build_object(" + ','.join(expressions) + '));\nROLLBACK;'


def verify(receipt, database, mode):
    authorize(database, mode)
    require(receipt.get('schema') == 1 and receipt.get('profile') == 'before_initialization_contract'
        and receipt.get('database') == database and receipt.get('mode') == mode
        and receipt.get('discovery_query_sha256') == sha(DISCOVERY_QUERY.encode()), 'sealed-pre-initialization-receipt-required')
    discovery = receipt['discovery']
    metadata = validate_metadata(discovery, database, mode)
    current = receipt['snapshot']
    require(validate_metadata(current, database, mode) == metadata,
        'catalog-changed-between-discovery-and-atomic-counts')
    require(receipt.get('capture_query_sha256') == sha(capture_query(metadata).encode()), 'atomic-null-count-query-differs')
    counts = current.get('null_counts')
    require(isinstance(counts, dict) and set(counts) == set(TABLES), 'exact-two-null-counts-required')
    for table in TABLES:
        if metadata[table] is None:
            require(counts[table] is None, 'absent-cold-table-cannot-claim-row-or-null-count')
        else:
            actual = counts[table]
            require(isinstance(actual, dict) and set(actual) == {'rows', 'null_rows'}
                and type(actual['rows']) is int and actual['rows'] >= 0
                and type(actual['null_rows']) is int and actual['null_rows'] == 0,
                'existing-company-or-line-name-null-blocks-first-initialization:' + table)
    for key in ('actual_readonly', 'atomic_catalog_and_null_counts', 'catalog_discovery_compared', 'before_candidate_initialization_contract'):
        require(receipt.get(key) is True, 'required-first-initialization-boundary-not-proven:' + key)
    for key in ('orm_loaded', 'payroll_values_read', 'salary_amounts_read', 'database_writes',
            'defaults_materialized', 'existing_values_converted', 'jsonb_line_conversion_admitted',
            'initializer_chronology_proven_by_helper', 'financial_certified', 'integral_conversion', 'deadline_resolved'):
        require(receipt.get(key) is False, 'unsafe-or-unproven-first-initialization-flag:' + key)
    return {'tables_present': [table for table in TABLES if metadata[table] is not None],
        'tables_absent_cold_only': [table for table in TABLES if metadata[table] is None],
        'null_counts': counts, 'company_source_not_null_required': mode != 'cold-community',
        'line_name_type_required': 'character varying', 'line_name_not_null_required': True,
        'no_null_backfill_admitted': True, 'no_jsonb_line_conversion_admitted': True}


def capture(readonlySQL, database, mode):
    """Two controlled calls; the final catalog+NULL counts share ONE RR/RO tx.

    Discovery avoids parsing a reference to an absent cold table. A concurrent
    create/drop/type change either fails SQL or changes the second metadata and
    aborts. No metadata/count from different snapshots is silently combined.
    """
    authorize(database, mode)
    discovery = json.loads(readonlySQL(database, DISCOVERY_QUERY))
    metadata = validate_metadata(discovery, database, mode)
    query = capture_query(metadata)
    snapshot = json.loads(readonlySQL(database, query))
    receipt = {'schema': 1, 'profile': 'before_initialization_contract', 'database': database, 'mode': mode,
        'discovery_query_sha256': sha(DISCOVERY_QUERY.encode()), 'capture_query_sha256': sha(query.encode()),
        'discovery': discovery, 'snapshot': snapshot, 'actual_readonly': True,
        'atomic_catalog_and_null_counts': True, 'catalog_discovery_compared': True,
        'before_candidate_initialization_contract': True, 'initializer_chronology_proven_by_helper': False,
        'orm_loaded': False, 'payroll_values_read': False,
        'salary_amounts_read': False, 'null_presence_counted': True, 'database_writes': False,
        'defaults_materialized': False, 'existing_values_converted': False, 'jsonb_line_conversion_admitted': False,
        'financial_certified': False, 'integral_conversion': False, 'deadline_resolved': False}
    receipt['observed'] = verify(receipt, database, mode)
    return receipt
