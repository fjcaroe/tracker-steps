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


def require_private(env):
    if not re.fullmatch(r"COMMUNITY_SYS_LINE_HISTORY_[A-Z0-9]+", env.cr.dbname):
        raise ValueError("A dedicated private Community line rehearsal database is required")
    assert not env["ir.module.module"].search_count([("state", "=", "installed"), ("license", "=", "OEEL-1")])
    assert env["ir.module.module"].search_count([("state", "=", "installed"), ("name", "=", "payroll")]) == 1


def snapshot(env):
    result = {}
    for model in ("hr.payslip", "hr.contract", "hr.salary.rule", *FIELDS):
        query = sql.SQL("SELECT to_jsonb(t) - %s::text[] FROM {} t ORDER BY id").format(
            sql.Identifier(env[model]._table))
        env.cr.execute(query, (list(FIELDS.get(model, ())),))
        encoded = json.dumps(env.cr.fetchall(), sort_keys=True).encode()
        result[model] = hashlib.sha256(encoded).hexdigest()
    env.cr.execute("""
        SELECT to_jsonb(a) FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id
        WHERE m.model=ANY(%s) ORDER BY a.id
    """, (list(FIELDS),))
    result["model_access"] = hashlib.sha256(json.dumps(env.cr.fetchall(), sort_keys=True).encode()).hexdigest()
    return result


def prepare(env):
    require_private(env)
    assert not env["ir.module.module"].search_count([("name", "=", MODULE), ("state", "=", "installed")])
    for model in ("hr.payslip", *FIELDS):
        env.cr.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(env[model]._table)))
        assert env.cr.fetchone() == (0,), "Only a fresh, empty Cerro payroll derivative can receive this fixture"
    slip = run_case(env, CASES[1], True, {}, MARKER)
    assert slip.line_ids and slip.input_line_ids and slip.worked_days_line_ids
    slip.write({"state": "done"})
    env.flush_all()
    before = snapshot(env)
    # Reproduce the SyS source layout. These columns only contain the new
    # fixture. Their absence is part of what the installation must handle.
    for model, names in FIELDS.items():
        changes = sql.SQL(", ").join(sql.SQL("DROP COLUMN {}").format(sql.Identifier(name)) for name in names)
        env.cr.execute(sql.SQL("ALTER TABLE {} {}").format(sql.Identifier(env[model]._table), changes))
    env.cr.commit()
    return before


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
    assert module.installed_version == "18.0.1.1.0"
    scope = env["hr.payslip"].with_user(7).with_context(tracking_disable=True, lang="en_US")
    history = scope.search([("name", "=", MARKER)])
    history.ensure_one()
    assert history.state == "done" and snapshot(env) == before
    rows = (history.line_ids, history.input_line_ids, history.worked_days_line_ids)
    counts = {}
    for records in rows:
        names = FIELDS[records._name]
        assert all(not records._fields[name].required and not records._fields[name].default for name in names)
        originals = records.read(list(names))
        assert originals and all(row[name] is False for row in originals for name in names)
        counts[records._name] = len(records)
        rejected(lambda: records.write({"name": MARKER + "_FORBIDDEN"}), UserError, "Closed payroll history")
    env.flush_all()
    assert snapshot(env) == before

    progress = {}
    slip = run_case(env, CASES[1], True, progress, MARKER + "_NEW", contract=history.contract_id,
                    period=(date(2026, 12, 1), date(2026, 12, 31)))
    assert all(line.code == line.input_type_id.code for line in slip.input_line_ids)
    assert all(day.code == day.work_entry_type_id.code for day in slip.worked_days_line_ids)
    calculated = slip.line_ids
    for line in calculated:
        for name in FIELDS["hr.payslip.line"]:
            assert line[name] and line[name] == line.salary_rule_id[name]
    for records in (calculated, slip.input_line_ids, slip.worked_days_line_ids):
        for name in FIELDS[records._name]:
            rejected(lambda: records.write({name: False}), ValidationError, "cannot be cleared")
    rule = calculated[0].salary_rule_id
    values = {"slip_id": slip.id, "contract_id": slip.contract_id.id, "employee_id": slip.employee_id.id,
              "name": MARKER, "code": rule.code, "salary_rule_id": rule.id, "category_id": rule.category_id.id}
    lines = slip.env["hr.payslip.line"]
    defaults = lines.default_get(list(FIELDS[lines._name]))
    manual = lines.create(values)
    assert all(manual[name] == defaults[name] and manual[name] for name in FIELDS[lines._name])
    manual.write({"amount_select": "percentage"})
    assert manual.amount_select == "percentage"
    for name in FIELDS[lines._name]:
        count = lines.search_count([("slip_id", "=", slip.id)])
        rejected(lambda: lines.create([values, dict(values, **{name: False})]),
                 ValidationError, "New payroll rows require")
        assert lines.search_count([("slip_id", "=", slip.id)]) == count
    env.cr.rollback()
    assert snapshot(env) == before and not scope.search_count([("name", "=", MARKER + "_NEW")])
    return {"uid": scope.env.uid, "legacy_rows_checked": counts, "fields": sum(map(len, FIELDS.values())),
            "computed_draft_lines": len(calculated.ids), "six_original_table_projections_and_acl_preserved": True,
            "closed_rows_preserved": True, "atomic_mixed_create": True, "rehearsal_rolled_back": True}
