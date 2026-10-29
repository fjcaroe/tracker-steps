"""Lossless literal-base projections; no configuration import or payroll execution.

The internal migration requires an actual Community/OCA engine, independently
of the database's name. The private rehearsal wrapper additionally checks its
database prefix. Operational callers own the lock, surrounding transaction,
backup and full preservation comparison. Neither entry point commits.
"""
import re

BASE_LANGUAGE = "en_US"
_UNSET = object()


class TranslationStorageError(ValueError):
    """Code-only failures: do not include original text or translated values."""


def literal_base(value):
    """Use en_US as Odoo's technical fallback, without translating the text."""
    if value is None:
        return None
    if isinstance(value, str):
        return {BASE_LANGUAGE: value}
    if isinstance(value, dict) and isinstance(value.get(BASE_LANGUAGE), str):
        if all(isinstance(key, str) and key and (item is None or isinstance(item, str))
                for key, item in value.items()):
            return dict(value)
    raise TranslationStorageError("unsupported-translation-shape")


def original_translation_payload(original, existing=_UNSET):
    """Plan a value only; never overwrite a different existing translation."""
    source = literal_base(original)
    if existing is _UNSET:
        return source
    current = literal_base(existing)
    if source is None:
        if current is not None:
            raise TranslationStorageError("source-null-conflicts-with-existing-translations")
        return None
    if current is None:
        return source
    result = dict(current)
    for language, value in source.items():
        if language in result and result[language] != value:
            raise TranslationStorageError("existing-translation-conflict")
        result[language] = value
    return result


def _table_identifier(table):
    from psycopg2 import sql

    names = table if isinstance(table, tuple) else (table,)
    if not all(re.fullmatch(r"[a-z_][a-z0-9_]*", name) for name in names):
        raise TranslationStorageError("unsafe-storage-identifier")
    return sql.Identifier(*names)


def _column_contract(cursor, table, column):
    relation = ".".join(table) if isinstance(table, tuple) else table
    cursor.execute("""SELECT t.typname,a.attnotnull,a.atthasdef FROM pg_attribute a
        JOIN pg_type t ON t.oid=a.atttypid WHERE a.attrelid=to_regclass(%s)
        AND a.attname=%s AND a.attnum>0 AND NOT a.attisdropped""", (relation, column))
    found = cursor.fetchone()
    if not found:
        raise TranslationStorageError("original-translation-column-missing")
    return found


def _projection(cursor, table, column, legacy=False):
    from psycopg2 import sql

    value = sql.Identifier(column)
    if legacy:
        value = sql.SQL("CASE WHEN {0} IS NULL THEN NULL ELSE jsonb_build_object('en_US',{0}) END").format(value)
    cursor.execute(sql.SQL("""SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(
        jsonb_build_object('id',id,'value',{})::text,E'\n' ORDER BY id),''),'UTF8')),'hex') FROM {}""").format(
            value, _table_identifier(table)))
    return cursor.fetchone()


def _validate_json(cursor, table, column):
    from psycopg2 import sql

    table_sql, column_sql = _table_identifier(table), sql.Identifier(column)
    cursor.execute(sql.SQL("SELECT 1 FROM {} WHERE {} IS NOT NULL AND jsonb_typeof({}) IS DISTINCT FROM 'object' LIMIT 1").format(
        table_sql, column_sql, column_sql))
    if cursor.fetchone():
        raise TranslationStorageError("translated-storage-must-be-object-or-null")
    cursor.execute(sql.SQL("""SELECT 1 FROM {} WHERE {} IS NOT NULL AND (
        jsonb_typeof({}->'en_US') IS DISTINCT FROM 'string' OR EXISTS (
            SELECT 1 FROM jsonb_each({}) item WHERE item.key='' OR jsonb_typeof(item.value) NOT IN ('string','null')))
        LIMIT 1""").format(table_sql, column_sql, column_sql, column_sql))
    if cursor.fetchone():
        raise TranslationStorageError("translated-storage-has-no-lossless-base")


def _convert_literal_column(cursor, table, column):
    """Internal primitive, also exercised on temporary real PostgreSQL tables."""
    from psycopg2 import sql

    kind, required, has_default = _column_contract(cursor, table, column)
    if kind not in {"text", "varchar", "jsonb"}:
        raise TranslationStorageError("unsupported-original-translation-column-type")
    if kind != "jsonb" and has_default:
        raise TranslationStorageError("original-translation-sql-default-needs-explicit-policy")
    before = _projection(cursor, table, column, legacy=kind != "jsonb")
    if kind != "jsonb":
        cursor.execute(sql.SQL("""ALTER TABLE {0} ALTER COLUMN {1} TYPE jsonb USING
            CASE WHEN {1} IS NULL THEN NULL ELSE jsonb_build_object('en_US',{1}) END""").format(
                _table_identifier(table), sql.Identifier(column)))
    _validate_json(cursor, table, column)
    after = _projection(cursor, table, column)
    if before != after or _column_contract(cursor, table, column) != ("jsonb", required, has_default):
        raise TranslationStorageError("original-translation-projection-changed")
    return {"converted": kind != "jsonb", "source_type": kind, "rows": before[0],
        "literal_projection_sha256": before[1], "required_preserved": True}


def migrate_original_translation_storage(cursor):
    """Internal product migration; no lab-name requirement or engine bypass."""
    cursor.execute("""SELECT 1 FROM ir_module_module WHERE state IN ('installed','to upgrade','to install','to remove')
        AND (license='OEEL-1' OR name='hr_payroll') LIMIT 1""")
    if cursor.fetchone():
        raise TranslationStorageError("native-engine-or-enterprise-target-not-admitted")
    cursor.execute("SELECT 1 FROM ir_module_module WHERE name='payroll' AND state IN ('installed','to upgrade')")
    if not cursor.fetchone():
        raise TranslationStorageError("actual-oca-reference-required")
    cursor.execute("SAVEPOINT step_original_translation_storage")
    try:
        cursor.execute("LOCK TABLE public.hr_salary_rule,public.hr_payslip_input_type IN ACCESS EXCLUSIVE MODE")
        result = {
            "hr.salary.rule.note": _convert_literal_column(cursor, ("public", "hr_salary_rule"), "note"),
            "hr.payslip.input.type.name": _convert_literal_column(cursor, ("public", "hr_payslip_input_type"), "name"),
        }
    except Exception:
        cursor.execute("ROLLBACK TO SAVEPOINT step_original_translation_storage")
        cursor.execute("RELEASE SAVEPOINT step_original_translation_storage")
        raise
    cursor.execute("RELEASE SAVEPOINT step_original_translation_storage")
    return {"columns": result, "base_language": BASE_LANGUAGE, "historical_lines_changed": False,
        "metadata_or_xmlids_changed": False, "rules_evaluated": False, "configuration_imported": False}


def prepare_original_translation_storage(cursor):
    """Private CLI/rehearsal admission, delegating to the same engine checks."""
    database = getattr(cursor, "dbname", None)
    if database is None:
        database = cursor.connection.info.dbname
    if not re.fullmatch(r"COMMUNITY_PAYROLL_API_[A-Za-z0-9_]+", database):
        raise TranslationStorageError("private-community-reference-required")
    return migrate_original_translation_storage(cursor)
