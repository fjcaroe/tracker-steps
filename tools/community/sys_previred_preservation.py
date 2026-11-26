"""Compare original SyS payroll storage on isolated copies before Odoo and after.

The coordinator holds the shared lock and keeps other writers off both copies.
Sequence state is outside PostgreSQL MVCC. Receipts contain counts and hashes,
never row values. This is a literal storage gate, separate from the v98 replay.
"""
import json
import re

from preflight_original_history_storage import authorize, require


TABLES = (
    'hr_payslip', 'hr_payslip_line', 'hr_payslip_worked_days', 'hr_payslip_input',
    'hr_payslip_run', 'hr_work_entry', 'hr_work_entry_type', 'hr_payslip_input_type',
    'hr_payroll_structure', 'hr_salary_rule', 'hr_salary_rule_category',
    'hr_contract', 'hr_employee', 'res_company', 'resource_calendar',
    'account_move', 'account_move_line', 'ir_sequence', 'ir_sequence_date_range',
    'ir_model_access', 'ir_rule', 'rule_group_rel', 'res_groups_users_rel',
    'res_groups_implied_rel', 'ir_model_data',
)
COUNTER = re.compile(r'ir_sequence_[0-9]+(?:_[0-9]+)?')
IDENTIFIER = re.compile(r'[a-z_][a-z0-9_]*')


def identifier(name):
    require(IDENTIFIER.fullmatch(name), 'sys-preservation-invalid-identifier')
    return '"' + name + '"'


def metadata_query():
    tables = ','.join("'" + table + "'" for table in TABLES)
    return f"""
SELECT json_build_object(
  'database', current_database(),
  'readonly', current_setting('transaction_read_only'),
  'isolation', current_setting('transaction_isolation'),
  'columns', (SELECT json_object_agg(relname, columns) FROM (
    SELECT c.relname, json_object_agg(a.attname, json_build_array(
      format_type(a.atttypid, a.atttypmod), a.attnotnull)) AS columns
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid
    WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname IN ({tables})
      AND a.attnum > 0 AND NOT a.attisdropped GROUP BY c.relname
  ) catalog),
  'foreign_keys', (SELECT coalesce(json_object_agg(
      c.relname || '.' || k.conname, json_build_array(pg_get_constraintdef(k.oid),
      k.convalidated)), '{{}}') FROM pg_constraint k
    JOIN pg_class c ON c.oid = k.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname IN ({tables}) AND k.contype = 'f'),
  'counters', (SELECT coalesce(json_agg(sequencename ORDER BY sequencename), '[]')
    FROM pg_sequences WHERE schemaname = 'public'
      AND sequencename ~ '^ir_sequence_[0-9]+(_[0-9]+)?$')
)
"""


def projection_query(table, columns):
    require(table in TABLES and bool(columns), 'sys-preservation-unknown-projection')
    selected = ', '.join(identifier(name) for name in sorted(columns))
    return f"""
SELECT json_build_object('rows', count(*), 'sha256',
  encode(sha256(convert_to(coalesce(string_agg(row_hash, '' ORDER BY row_hash), ''), 'UTF8')), 'hex'))
FROM (SELECT encode(sha256(convert_to(to_jsonb(original)::text, 'UTF8')), 'hex') AS row_hash
  FROM (SELECT {selected} FROM public.{identifier(table)}) original) hashed
"""


def capture(cursor, database, baseline=None):
    """Read inside a single repeatable-read, read-only transaction."""
    authorize(database, 'sys-previred')
    cursor.execute("SET LOCAL search_path = pg_catalog, public")
    cursor.execute(metadata_query())
    snapshot = cursor.fetchone()[0]
    require(snapshot['database'] == database and snapshot['readonly'] == 'on'
            and snapshot['isolation'] == 'repeatable read', 'sys-preservation-readonly-transaction-required')
    snapshot['columns'] = snapshot['columns'] or {}
    originals = baseline['columns'] if baseline else snapshot['columns']
    require(set(originals) == set(TABLES), 'sys-preservation-original-tables-missing')
    snapshot['projections'] = {}
    for table, columns in originals.items():
        if not set(columns) <= set(snapshot['columns'].get(table, {})):
            continue
        cursor.execute(projection_query(table, columns))
        snapshot['projections'][table] = cursor.fetchone()[0]
    counters = {}
    for name in snapshot['counters']:
        require(COUNTER.fullmatch(name), 'sys-preservation-invalid-counter')
        cursor.execute(f'SELECT last_value, is_called FROM public.{identifier(name)}')
        counters[name] = list(cursor.fetchone())
    snapshot['counters'] = counters
    if baseline is None:
        require(all(snapshot['projections'][table]['rows'] > 0
                    for table in ('hr_payslip', 'hr_payslip_line')), 'sys-preservation-original-history-required')
    return snapshot


def differences(before, after):
    """List changed originals. Added columns, FK and counters are separate schema review."""
    columns = [
        f'{table}.{name}'
        for table, definitions in sorted(before['columns'].items())
        for name, definition in sorted(definitions.items())
        if after['columns'].get(table, {}).get(name) != definition
    ]
    changed = {'columns': columns}
    for section in ('projections', 'foreign_keys', 'counters'):
        changed[section] = sorted(
            key for key, value in before[section].items() if after[section].get(key) != value)
    return changed
