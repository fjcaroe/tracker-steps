"""Catalog-only admission for original unlimited NUMERIC input amounts.

No amount is read, cast, rounded, filled or written. Existing Float8 is refused
even when empty: its historical conversion requires a separate approved plan.
Operational callers own the backup, shared lease and outer transaction.
"""
import re


class InputStorageError(ValueError):
    """Code-only storage failures; never include payroll amounts or labels."""


def admit_input_amount_contract(column):
    """Pure policy over actual PostgreSQL catalog facts, not field defaults."""
    if column["type"] == "float8":
        raise InputStorageError("existing-float8-input-amount-needs-lossless-conversion-plan")
    if column["type"] != "numeric" or column["type_kind"] != "b":
        raise InputStorageError("original-input-amount-must-use-base-numeric")
    if column["typmod"] != -1:
        raise InputStorageError("original-input-amount-fixed-precision-not-admitted")
    if column["not_null"]:
        raise InputStorageError("original-input-amount-must-preserve-nullability")
    if column["has_default"]:
        raise InputStorageError("original-input-amount-sql-default-needs-explicit-policy")
    return True


def inspect_input_amount_storage(cursor, table=("public", "hr_payslip_input")):
    """Read only catalog facts; the TEMP-table path is for functional tests."""
    if not (isinstance(table, tuple) and 1 <= len(table) <= 2
            and all(re.fullmatch(r"[a-z_][a-z0-9_]*", part) for part in table)):
        raise InputStorageError("unsafe-input-storage-identifier")
    relation = ".".join(table)
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL", (relation,))
    if not cursor.fetchone()[0]:
        return None
    cursor.execute("""SELECT t.typname,t.typtype,a.atttypmod,a.attnotnull,a.atthasdef
        FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid
        WHERE a.attrelid=to_regclass(%s) AND a.attname='amount'
        AND a.attnum>0 AND NOT a.attisdropped""", (relation,))
    row = cursor.fetchone()
    if row is None:
        raise InputStorageError("original-input-amount-column-missing")
    column = dict(zip(("type", "type_kind", "typmod", "not_null", "has_default"), row))
    admit_input_amount_contract(column)
    return column


def input_amount_table_admission(api_state, present):
    if api_state not in {"to install", "installed", "to upgrade"}:
        raise InputStorageError("payroll-api-module-state-not-admitted")
    if not present and api_state != "to install":
        raise InputStorageError("original-input-table-missing-on-upgrade")
    return {"input_table_pending_orm": not present}


def admit_original_input_storage(cursor):
    """Product entry point before ORM setup; no lab-name or engine bypass."""
    cursor.execute("""SELECT 1 FROM ir_module_module WHERE state IN ('installed','to upgrade','to install','to remove')
        AND (license='OEEL-1' OR name='hr_payroll') LIMIT 1""")
    if cursor.fetchone():
        raise InputStorageError("native-engine-or-enterprise-target-not-admitted")
    cursor.execute("SELECT 1 FROM ir_module_module WHERE name='payroll' AND state IN ('installed','to upgrade')")
    if not cursor.fetchone():
        raise InputStorageError("actual-oca-reference-required")
    cursor.execute("SELECT state FROM ir_module_module WHERE name='step_payroll_oca_api'")
    state = cursor.fetchone()
    column = inspect_input_amount_storage(cursor)
    admission = input_amount_table_admission(state[0] if state else None, column is not None)
    return dict(admission, status="cold-real-orm-pending" if column is None else "original-numeric-preserved",
        column=column, target_type="numeric", target_typmod=-1, stored_amounts_read=False,
        amounts_changed=False, nulls_changed=False, ddl_executed=False,
        code_or_contract_materialized=False, engine_conversion=False)
