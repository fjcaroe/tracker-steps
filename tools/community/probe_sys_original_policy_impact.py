"""Evaluate the two official forward policy migrations without writing an original SyS rule."""
from collections import Counter
import hashlib
from itertools import product
from pathlib import Path
import runpy

from odoo.exceptions import AccessError
from odoo.osv.expression import normalize_domain
from odoo.tools.safe_eval import safe_eval


SCRIPTS = {"hr_timesheet": "9544564714f2bc5b2e21eaa34f7ffa46b12b454336c8849c3cf79adc7093b4fc",
           "project_sms": "d4f2b05e132913fe874c11cdf0619b633e439f894d3d04d66c39e488606124d0"}


def proposed(shell, core):
    cr = shell.cr
    cr.rollback()
    cr.execute("""SELECT r.id,d.module,d.name,m.model,r.domain_force
        FROM public.ir_model_data d JOIN public.ir_rule r ON r.id=d.res_id
        JOIN public.ir_model m ON m.id=r.model_id WHERE d.model='ir.rule'
        AND (d.module='hr_timesheet' AND d.name IN ('timesheet_line_rule_approver','timesheet_analysis_report_approver')
        OR d.module='project_sms' AND d.name='ir_rule_sms_template_project_manager') ORDER BY r.id""")
    originals = cr.fetchall()
    assert len(originals) == 3
    cr.execute("CREATE TEMP TABLE ir_rule (id integer PRIMARY KEY,domain_force text) ON COMMIT DROP")
    cr.execute("CREATE TEMP TABLE ir_model_data (res_id integer,model text,module text,name text) ON COMMIT DROP")
    cr.execute("SET LOCAL search_path=pg_temp,pg_catalog")
    cr.execute("SELECT 'ir_rule'::regclass='pg_temp.ir_rule'::regclass AND "
               "'ir_model_data'::regclass='pg_temp.ir_model_data'::regclass AND 'ir_rule'::regclass<>'public.ir_rule'::regclass")
    assert cr.fetchone() == (True,)
    for pk, module, name, model, domain in originals:
        cr.execute("INSERT INTO ir_rule VALUES (%s,%s)", (pk, domain))
        cr.execute("INSERT INTO ir_model_data VALUES (%s,'ir.rule',%s,%s)", (pk, module, name))
    for module, sha in SCRIPTS.items():
        path = core / "addons" / module / "upgrades/1.1/pre-migrate.py"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
        runpy.run_path(str(path))["migrate"](cr, "18.0.1.0")
    cr.execute("SELECT id,domain_force FROM ir_rule")
    after = dict(cr.fetchall())
    cr.rollback()
    assert all(after[r[0]] != r[4] for r in originals)
    return [(name, model, old, after[pk]) for pk, module, name, model, old in originals]


def evaluates(domain, case):
    stack = []
    for node in reversed(normalize_domain(domain)):
        if node in ("&", "|"):
            left, right = stack.pop(), stack.pop()
            stack.append(left and right if node == "&" else left or right)
        else:
            field, operator, operand = node
            val = case[field]
            if operator == "!=":
                stack.append(val != operand)
            else:
                assert operator == "in"
                stack.append(bool(set(val).intersection(operand)) if isinstance(val, list) else val in operand)
    assert len(stack) == 1
    return stack[0]


def synthetic(model, original, following, partner):
    if model == "sms.template":
        cases = [{"model": label, "model_id.model": label} for label in (
            "project.task.type", "project.project.stage", "project.task", "project.project", "res.partner")]
    else:
        cases = [{"project_id": 1, "project_id.privacy_visibility": visibility,
                  "project_id.message_partner_ids": [partner] if project_follower else [],
                  "task_id.message_partner_ids": [partner] if task_follower else []}
                 for visibility, project_follower, task_follower in product(("followers", "employees"), (False, True), (False, True))]
    pairs = [(evaluates(original, row), evaluates(following, row)) for row in cases]
    return {"cases": len(cases), "gained": pairs.count((False, True)), "lost": pairs.count((True, False))}


def run(shell, core):
    policies = proposed(shell, core)
    shell.cr.execute("SET TRANSACTION READ ONLY")
    users = shell["res.users"].sudo().search([("active", "=", True), ("share", "=", False), ("id", ">", 1)])
    assert len(users) == 2
    checks = {}
    for name, model, old, future in policies:
        gained, lost, scopes = set(), set(), Counter()
        fixtures = None
        for actor in users:
            for company in actor.company_ids.filtered("active"):
                scoped = shell(user=actor.id, su=False, context={"allowed_company_ids": [company.id]})
                assert not scoped.su and scoped.company.id == company.id
                ctx = {"user": scoped.user}
                before, after = safe_eval(old, ctx), safe_eval(future, ctx)
                sample = synthetic(model, before, after, scoped.user.partner_id.id)
                assert fixtures is None or sample == fixtures
                fixtures = sample
                obj = scoped[model]
                boundary = [("company_id", "in", [False, company.id])] if "company_id" in obj._fields else []
                try:
                    a = set(obj.search(before + boundary).ids)
                    b = set(obj.search(after + boundary).ids)
                except AccessError:
                    scopes["denied"] += 1
                    continue
                scopes["checked"] += 1
                if a != b:
                    scopes["different"] += 1
                gained.update((actor.id, pk) for pk in b - a)
                lost.update((actor.id, pk) for pk in a - b)
        checks[name] = {"model": model, "synthetic": fixtures, "original_operator_company_scopes": dict(scopes),
                        "additional_operator_records": len(gained), "removed_operator_records": len(lost)}
    shell.cr.rollback()
    return checks
