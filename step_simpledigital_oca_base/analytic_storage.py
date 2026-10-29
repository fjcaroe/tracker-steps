"""Admit the original rule property before Odoo initializes its JSON field.

Only the rule column is converted.  OCA's independent scalar field on salary
lines is deliberately untouched, including every closed historical line.
The caller owns the environment lease and must run this before field setup.
"""
import json


class AnalyticStorageError(ValueError):
    """The existing property cannot be adopted without choosing new ownership."""


def _require_community_provider(cr):
    cr.execute("SELECT to_regclass('ir_module_module')")
    if cr.fetchone()[0] is None:
        raise AnalyticStorageError("Payroll provider metadata must exist before analytic storage admission.")
    cr.execute("""SELECT name FROM ir_module_module
        WHERE state IN ('installed','to install','to upgrade','to remove')
        AND (license='OEEL-1' OR name IN ('hr_payroll','hr_payroll_account')) ORDER BY name""")
    if cr.fetchone():
        raise AnalyticStorageError("Adopt the complete native identity and retire Enterprise in an isolated conversion before analytic storage migration.")
    cr.execute("SELECT name FROM ir_module_module WHERE name IN ('payroll','payroll_account') AND state='installed'")
    if {row[0] for row in cr.fetchall()} != {"payroll", "payroll_account"}:
        raise AnalyticStorageError("The actual OCA payroll and payroll_account providers must be installed before analytic storage migration.")
    cr.execute("""SELECT c.relname,a.attname,t.typname FROM pg_class c
        JOIN pg_attribute a ON a.attrelid=c.oid JOIN pg_type t ON t.oid=a.atttypid
        WHERE c.oid=ANY(ARRAY[to_regclass('account_analytic_account'),to_regclass('res_company')])
        AND a.attnum>0 AND NOT a.attisdropped AND a.attname IN ('id','company_id')""")
    columns = {(table, name): kind for table, name, kind in cr.fetchall()}
    if any(columns.get(key) != "int4" for key in (
            ("account_analytic_account", "id"), ("account_analytic_account", "company_id"), ("res_company", "id"))):
        raise AnalyticStorageError("Original analytic account and company identity storage is unavailable.")
    cr.execute("""SELECT t.typname FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid
        WHERE a.attrelid=to_regclass('hr_payslip_line') AND a.attname='analytic_account_id'
        AND a.attnum>0 AND NOT a.attisdropped""")
    line = cr.fetchone()
    if line is not None and line != ("int4",):
        raise AnalyticStorageError("OCA salary-line analytic storage must remain its independent scalar column.")


def _storage_plan(cr):
    cr.execute("""SELECT t.typname,a.attnotnull,pg_get_expr(d.adbin,d.adrelid)
        FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid
        LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE a.attrelid=to_regclass('hr_salary_rule') AND a.attname='analytic_account_id'
        AND a.attnum>0 AND NOT a.attisdropped""")
    column = cr.fetchone()
    if column is None:
        return {"storage": "absent", "rows": [], "foreign_keys": []}
    kind, required, default = column
    if kind not in {"int4", "jsonb"} or required or default is not None:
        raise AnalyticStorageError("Original analytic rule storage must be nullable int4 or jsonb without a SQL default.")
    cr.execute("SELECT id,company_id FROM account_analytic_account")
    accounts = dict(cr.fetchall())
    cr.execute("SELECT id FROM res_company")
    companies = {row[0] for row in cr.fetchall()}
    cr.execute("""SELECT 1 FROM pg_attribute WHERE attrelid='hr_salary_rule'::regclass
        AND attname='company_id' AND attnum>0 AND NOT attisdropped""")
    owner = "company_id" if cr.fetchone() else "NULL::integer"
    cr.execute("SELECT id," + owner + ",analytic_account_id,analytic_account_id IS NULL FROM hr_salary_rule ORDER BY id")
    rows = cr.fetchall()
    converted = []

    def check_target(company, ident):
        if (not isinstance(company, int) or isinstance(company, bool) or company not in companies
                or not isinstance(ident, int) or isinstance(ident, bool) or not 0 < ident < 2**31
                or ident not in accounts or accounts[ident] not in (None, company)):
            raise AnalyticStorageError("Original analytic rule ownership or account reference is missing, ambiguous or incompatible.")

    for ident, company, value, sql_null in rows:
        if sql_null:
            continue  # SQL NULL is not an empty dictionary or a new owner.
        if kind == "int4":
            # A global rule has no authorized scalar-property owner.  Do not
            # infer one from the account, structure, creator or current user.
            check_target(company, value)
            converted.append((ident, {str(company): value}))
        else:
            if not isinstance(value, dict):
                raise AnalyticStorageError("Original analytic JSON property must be a company mapping.")
            for key, target in value.items():
                if (not isinstance(key, str) or not key.isdecimal() or str(int(key)) != key
                        or int(key) not in companies):
                    raise AnalyticStorageError("Original analytic JSON property has an invalid company key.")
                if target is not None and target is not False:
                    check_target(int(key), target)
    cr.execute("""SELECT c.conname,c.contype,c.conkey=ARRAY[a.attnum]::smallint[],
            c.confrelid='account_analytic_account'::regclass,
            c.confkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid='account_analytic_account'::regclass AND attname='id')]::smallint[],
            c.confdeltype
        FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attname='analytic_account_id'
        WHERE c.conrelid='hr_salary_rule'::regclass AND a.attnum=ANY(c.conkey)""")
    foreign_keys = []
    for name, constraint_type, single, target_table, target_id, deletion in cr.fetchall():
        if constraint_type != "f" or not single or not target_table or not target_id or deletion != "n":
            raise AnalyticStorageError("Unexpected original analytic column constraint; review it before conversion.")
        foreign_keys.append(name)
    return {"storage": kind, "rows": converted, "foreign_keys": foreign_keys, "count": len(rows)}


def migrate_original_analytic_storage(cr):
    """Convert only unambiguous CE scalar values; preserve existing JSON exactly.

    No salary, line, company, default, ID or sequence is written.  The complete
    plan is checked under a lock before any DDL, and a caught error cannot leave
    a partially converted schema.  Existing JSON, including NULL and empty
    mappings, is never rewritten; processing admission is a separate concern.
    """
    from psycopg2 import sql

    with cr.savepoint(flush=False):
        _require_community_provider(cr)
        cr.execute("SELECT to_regclass('hr_salary_rule')")
        if cr.fetchone()[0] is None:
            return {"storage": "absent", "converted": 0}
        cr.execute("LOCK TABLE hr_salary_rule IN ACCESS EXCLUSIVE MODE")
        plan = _storage_plan(cr)
        if plan["storage"] != "int4":
            return {"storage": plan["storage"], "converted": 0}
        for name in plan["foreign_keys"]:
            cr.execute(sql.SQL("ALTER TABLE hr_salary_rule DROP CONSTRAINT {}").format(sql.Identifier(name)))
        cr.execute("""ALTER TABLE hr_salary_rule ALTER COLUMN analytic_account_id
            TYPE jsonb USING to_jsonb(analytic_account_id)""")
        for ident, mapping in plan["rows"]:
            cr.execute("UPDATE hr_salary_rule SET analytic_account_id=%s::jsonb WHERE id=%s", (json.dumps(mapping), ident))
        return {"storage": "jsonb", "converted": len(plan["rows"])}


def prepare_original_analytic_storage(cr):
    """Same strict admission for callers preparing an isolated rehearsal."""
    return migrate_original_analytic_storage(cr)
