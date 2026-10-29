"""Pre-ORM admission for the one globally compatible NOT NULL constraint.

The ORM owns the actual type.name column and applies NOT NULL. This preflight
must run before field setup on both cold install and upgrades. It never fills
names, adopts configuration, commits or touches historical payroll lines.
"""
class NullableStorageError(ValueError):
    pass


def original_type_name_table_admission(api_state, present):
    if api_state not in {"to install", "installed", "to upgrade"}:
        raise NullableStorageError("payroll-api-module-state-not-admitted")
    if not present and api_state != "to install":
        raise NullableStorageError("original-structure-type-table-missing-on-upgrade")
    return {"type_table_pending_orm": not present}


def _check_original_type_names(cursor, table):
    """Only an identifier, for the actual table and isolated TEMP-table tests."""
    from psycopg2 import sql

    cursor.execute(sql.SQL("SELECT count(*) FROM {} WHERE name IS NULL").format(sql.Identifier(*table)))
    if cursor.fetchone()[0]:
        raise NullableStorageError("original-structure-type-name-null-no-backfill-admitted")
    cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(*table)))
    return {"rows": cursor.fetchone()[0], "null_names": 0, "names_changed": False}


def admit_original_nullable_storage(cursor):
    """Actual Community/OCA only; operational runners own backup and lease."""
    cursor.execute("""SELECT 1 FROM ir_module_module WHERE state IN ('installed','to upgrade','to install','to remove')
        AND (license='OEEL-1' OR name='hr_payroll') LIMIT 1""")
    if cursor.fetchone():
        raise NullableStorageError("native-engine-or-enterprise-target-not-admitted")
    cursor.execute("SELECT 1 FROM ir_module_module WHERE name='payroll' AND state IN ('installed','to upgrade')")
    if not cursor.fetchone():
        raise NullableStorageError("actual-oca-reference-required")
    cursor.execute("SELECT state FROM ir_module_module WHERE name='step_payroll_oca_api'")
    state = cursor.fetchone()
    cursor.execute("SELECT to_regclass('public.hr_payroll_structure_type') IS NOT NULL")
    admission = original_type_name_table_admission(state[0] if state else None, cursor.fetchone()[0])
    if admission["type_table_pending_orm"]:
        return dict(admission, status="absent-cold-real-orm-pending", names_changed=False)
    cursor.execute("LOCK TABLE public.hr_payroll_structure_type IN ACCESS EXCLUSIVE MODE")
    return dict(admission, **_check_original_type_names(cursor, ("public", "hr_payroll_structure_type")))
