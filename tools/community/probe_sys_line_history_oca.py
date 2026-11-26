"""Exercise SyS historical-field admission on a fresh private Cerro OCA derivative."""

from datetime import date
import hashlib
import json
import re

from psycopg2 import sql
from odoo.exceptions import UserError, ValidationError

from probe_original_draft_amounts import CASES, run_case


FIELDS = {
    "hr.payslip.line": ("amount_select", "condition_select", "condition_python"),
    "hr.payslip.input": ("code",),
    "hr.payslip.worked_days": ("code",),
}
MODULE = "step_payroll_oca_sys_history"
MARKER = "SYS_LINE_HISTORY_REHEARSAL"
STORAGE_FIELDS = {
    **FIELDS, "hr.payslip.run": ("journal_id",),
    "hr.payslip.input": ("code", "contract_id"), "hr.payslip.worked_days": ("code", "contract_id"),
}
RELATED = {
    "hr.payslip.input": {"code": ("input_type_id", "code"), "contract_id": ("payslip_id", "contract_id")},
    "hr.payslip.worked_days": {"code": ("work_entry_type_id", "code"), "contract_id": ("payslip_id", "contract_id")},
    "hr.payslip.line": {"amount_select": ("salary_rule_id", "amount_select")},
}


def require_private(env):
    if not re.fullmatch(r"COMMUNITY_SYS_LINE_HISTORY_[A-Z0-9]+", env.cr.dbname):
        raise ValueError("A dedicated private Community line rehearsal database is required")
    assert not env["ir.module.module"].search_count([("state", "=", "installed"), ("license", "=", "OEEL-1")])
    assert env["ir.module.module"].search_count([("state", "=", "installed"), ("name", "=", "payroll")]) == 1


def snapshot(env):
    result = {}
    for model in ("hr.payslip", "hr.contract", "hr.salary.rule", *STORAGE_FIELDS):
        query = sql.SQL("SELECT to_jsonb(t) - %s::text[] FROM {} t ORDER BY id").format(
            sql.Identifier(env[model]._table))
        env.cr.execute(query, (list(STORAGE_FIELDS.get(model, ())),))
        encoded = json.dumps(env.cr.fetchall(), sort_keys=True).encode()
        result[model] = hashlib.sha256(encoded).hexdigest()
    env.cr.execute("""
        SELECT to_jsonb(a) FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id
        WHERE m.model=ANY(%s) ORDER BY a.id
    """, (list(STORAGE_FIELDS),))
    result["model_access"] = hashlib.sha256(json.dumps(env.cr.fetchall(), sort_keys=True).encode()).hexdigest()
    return result


def prepare(env):
    require_private(env)
    assert not env["ir.module.module"].search_count([("name", "=", MODULE), ("state", "=", "installed")])
    for model in ("hr.payslip", *STORAGE_FIELDS):
        env.cr.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(env[model]._table)))
        assert env.cr.fetchone() == (0,), "Only a fresh, empty Cerro payroll derivative can receive this fixture"
    slip = run_case(env, CASES[1], True, {}, MARKER)
    assert slip.line_ids and slip.input_line_ids and slip.worked_days_line_ids
    journal = slip.env["account.journal"].search([("company_id", "=", slip.company_id.id),
                                                 ("type", "=", "general")], limit=1)
    assert journal
    batch = slip.env["hr.payslip.run"].create({"name": MARKER, "journal_id": journal.id})
    slip.write({"payslip_run_id": batch.id, "state": "done"})
    env.flush_all()
    before = snapshot(env)
    # Reproduce the SyS source layout. These columns only contain the new
    # fixture. Their absence is part of what the installation must handle.
    for model, names in STORAGE_FIELDS.items():
        changes = sql.SQL(", ").join(sql.SQL("DROP COLUMN {}").format(sql.Identifier(name)) for name in names)
        env.cr.execute(sql.SQL("ALTER TABLE {} {}").format(sql.Identifier(env[model]._table), changes))
    env.cr.commit()
    return before


def initialize_provider(env, before):
    require_private(env)
    assert not env["ir.module.module"].search_count([("name", "=", MODULE), ("state", "=", "installed")])
    for model, names in STORAGE_FIELDS.items():
        env.cr.execute("SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass "
                       "AND attname=ANY(%s) AND NOT attisdropped", (env[model]._table, list(names)))
        assert not env.cr.fetchall()
        for name in names:
            field = env[model]._fields[name]
            if name in RELATED.get(model, {}):
                assert not field.store
            else:
                assert not field.required and not field.default
    env.registry.init_models(env.cr, list(STORAGE_FIELDS), {})
    for model, names in STORAGE_FIELDS.items():
        physical = sorted(set(names) - RELATED.get(model, {}).keys())
        env.cr.execute("SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass "
                       "AND attname=ANY(%s) AND NOT attisdropped ORDER BY attname", (env[model]._table, list(names)))
        assert [row[0] for row in env.cr.fetchall()] == physical
        if physical:
            env.cr.execute(sql.SQL("SELECT count(*), count(*) FILTER (WHERE {}) FROM {}").format(
                sql.SQL(" AND ").join(sql.SQL("{} IS NULL").format(sql.Identifier(name)) for name in physical),
                sql.Identifier(env[model]._table)))
            total, unknown = env.cr.fetchone()
            assert total > 0 and total == unknown
    assert snapshot(env) == before
    env.cr.commit()


def rejected(operation, exception, expected):
    try:
        operation()
    except exception as error:
        assert expected in str(error), type(error).__name__
    else:
        raise AssertionError("The guarded payroll operation unexpectedly succeeded")


def verify(env, before):
    require_private(env)
    module = env["ir.module.module"].search([("name", "=", MODULE), ("state", "=", "installed")])
    assert module.installed_version == "18.0.1.2.0"
    scope = env["hr.payslip"].with_user(7).with_context(tracking_disable=True, lang="en_US")
    history = scope.search([("name", "=", MARKER)])
    history.ensure_one()
    assert history.state == "done" and snapshot(env) == before
    assert history.payslip_run_id.name == MARKER and not history.payslip_run_id.journal_id
    rows = (history.line_ids, history.input_line_ids, history.worked_days_line_ids)
    counts = {}
    for records in rows:
        names = FIELDS[records._name]
        for name, related in RELATED[records._name].items():
            field = records._fields[name]
            assert field.related == ".".join(related) and not field.store and field.readonly and not field.copy
            for row in records:
                assert row[name] == row[related[0]][related[1]]
        for name in set(names) - RELATED[records._name].keys():
            assert all(not record[name] for record in records)
        env.cr.execute("SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attname=ANY(%s) "
                       "AND NOT attisdropped", (records._table, list(RELATED[records._name])))
        assert not env.cr.fetchall()
        counts[records._name] = len(records)
        rejected(lambda: records.write({"name": MARKER + "_FORBIDDEN"}), UserError, "Closed payroll history")
    env.flush_all()
    assert snapshot(env) == before
    report_model = history.env["report.step_simpledigital_oca_base.report_payslip"]
    report = report_model._get_report_values(history.ids)
    for day in report["step_report_days"](history):
        assert report["step_report_day_value"](day, "code") == day.work_entry_type_id.code
    assert snapshot(env) == before

    progress = {}
    slip = run_case(env, CASES[1], True, progress, MARKER + "_NEW", contract=history.contract_id,
                    period=(date(2026, 12, 1), date(2026, 12, 31)))
    assert all(line.code == line.input_type_id.code for line in slip.input_line_ids)
    assert all(day.code == day.work_entry_type_id.code for day in slip.worked_days_line_ids)
    assert slip._step_check_saved_input_values()
    calculated = slip.line_ids
    for line in calculated:
        for name in FIELDS["hr.payslip.line"]:
            assert line[name] and line[name] == line.salary_rule_id[name]
    for records in (calculated, slip.input_line_ids, slip.worked_days_line_ids):
        for name in FIELDS[records._name]:
            expected = "related payroll field" if name in RELATED[records._name] else "cannot be cleared"
            rejected(lambda: records.write({name: False}), ValidationError, expected)
    # An old draft may already have stored amounts and no codes or formula
    # snapshot. Refuse to replace those original lines on a recalculation.
    for field in ("condition_select", "condition_python"):
        with env.cr.savepoint() as trial:
            env.cr.execute(sql.SQL("UPDATE {} SET {}=NULL WHERE id=%s").format(
                sql.Identifier(calculated._table), sql.Identifier(field)), (calculated[0].id,))
            calculated.invalidate_recordset([field])
            original = snapshot(env)
            rejected(slip.compute_sheet, UserError, "missing historical payroll codes")
            assert snapshot(env) == original
            trial.rollback()
    rule = calculated[0].salary_rule_id
    values = {"slip_id": slip.id, "contract_id": slip.contract_id.id, "employee_id": slip.employee_id.id,
              "name": MARKER, "code": rule.code, "salary_rule_id": rule.id, "category_id": rule.category_id.id}
    lines = slip.env["hr.payslip.line"]
    defaults = lines.default_get(list(FIELDS[lines._name]))
    manual = lines.create(values)
    assert manual.amount_select == rule.amount_select
    assert all(manual[name] == defaults[name] and manual[name] for name in ("condition_select", "condition_python"))
    manual.write({"condition_select": "range"})
    assert manual.condition_select == "range"
    for name in ("condition_select", "condition_python"):
        count = lines.search_count([("slip_id", "=", slip.id)])
        rejected(lambda: lines.create([values, dict(values, **{name: False})]),
                 ValidationError, "New payroll rows require")
        assert lines.search_count([("slip_id", "=", slip.id)]) == count
    env.cr.rollback()
    assert snapshot(env) == before and not scope.search_count([("name", "=", MARKER + "_NEW")])
    return {"uid": scope.env.uid, "legacy_rows_checked": counts, "fields": sum(map(len, FIELDS.values())),
            "computed_draft_lines": len(calculated.ids), "seven_original_table_projections_and_acl_preserved": True,
            "closed_rows_preserved": True, "five_nonstored_related_fields": True,
            "atomic_mixed_create": True, "rehearsal_rolled_back": True}
