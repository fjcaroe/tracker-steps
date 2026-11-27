"""Verify native operator forms, metadata-only upgrades and payroll results on the U48 memory derivative."""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
import subprocess
import tempfile

from compare_sys_company_drafts import compare
from exercise_sys_193 import FROZEN_FINANCE, FROZEN_LOG
from prepare_sys_payslip_form_trial import DB, WORK, odoo
from inspect_sys_absence_chain import TARGET as HISTORY_REFERENCE
from seal_local_sys_193 import CODE, PORT, SOCKET, capture, psql, sha


def shell(label, script):
    setup = "import sys,json\nsys.path.insert(0," + repr(str(CODE)) + ")\nassert env.cr.dbname==" + repr(DB) + "\n"
    try:
        result = odoo(["shell"], (setup + script).encode())
    except subprocess.CalledProcessError as exc:
        (WORK / (label + ".stderr")).write_bytes(exc.stderr)
        (WORK / (label + ".stdout")).write_bytes(exc.stdout)
        raise
    (WORK / (label + ".stderr")).write_bytes(result.stderr)
    (WORK / (label + ".stdout")).write_bytes(result.stdout)
    return result.stdout


def payroll(refs, *, version="18.0.1.6.2", runner=shell):
    source = refs / "U43C/wsl-finance-reference"
    if sha(source / "finance.py") != FROZEN_FINANCE or sha(source / "finance.log") != FROZEN_LOG:
        raise ValueError("Unrecognized financial reference")
    script = (source / "finance.py").read_text()
    versions = "'step_payroll_oca_sys_history':'18.0.1.6.1'"
    if script.count(versions) != 1:
        raise ValueError("Unrecognized version assertion")
    if version not in ("18.0.1.6.2", "18.0.1.6.3"):
        raise ValueError("Unknown version in SyS payroll comparison")
    raw = runner("payroll", script.replace(versions, versions.replace("18.0.1.6.1", version)))
    def entries(content):
        return {name.decode(): json.loads(body) for name, body in
                (line.split(b" ", 1) for line in content.splitlines() if line.startswith(b"SYSL_"))}
    reference = entries((source / "finance.log").read_bytes())
    actual = entries(raw)
    if len(actual) != 10 or actual.keys() != reference.keys():
        raise ValueError("Incomplete payroll trial")
    for key in actual.keys() - {"SYSL_VERSIONS"}:
        if actual[key] != reference[key]:
            raise ValueError("Original payroll scenario differs: " + key)
    native = json.loads((refs / "U40/U40R17POSTALL-native-companies.json").read_bytes())
    rows = compare(native, actual["SYSL_COMPANIES"], accounting=True, require_review_policy=True)
    total = sum(rows.values(), Counter())
    assert len(rows) == 12 and (total["selected"], total["same_calculation"], total["both_rejected"],
                                total["matching_confirmations"]) == (133, 130, 3, 130)
    return {"companies": len(rows), "results": dict(total), "scenarios": len(actual) - 1}


def form(refs=None):
    here = Path(__file__).resolve().parent
    script = (here / "probe_sys_absence_approvers.py").read_text() + "\n" + (here / "probe_sys_payslip_operator_form.py").read_text()
    check = "operator_forms(env)"
    if refs is not None:
        oracle = refs / "U43C/wsl-finance-reference/finance.log"
        assert sha(oracle) == FROZEN_LOG
        days, = [json.loads(line.split(b" ", 1)[1]) for line in oracle.read_bytes().splitlines() if line.startswith(b"SYSL_DAYS ")]
        cases = [(row["source_slip"], row["draft_sha256"]) for row in days["rows"] if row["day_source"] == "current_work_entries"]
        assert len(cases) == 5
        check = "october_forms(env, " + repr(cases) + ")"
    raw = shell("october" if refs is not None else "form", script + "\nprint('SYS '+json.dumps(" + check + "),flush=True)\n")
    found = [json.loads(line[4:]) for line in raw.splitlines() if line.startswith(b"SYS ")]
    if len(found) != 1:
        raise ValueError("Expected one real operator result")
    return found[0]


def postflight():
    before = json.loads(gzip.decompress((WORK / "before/snapshot.json.gz").read_bytes()))
    folder = Path(tempfile.mkdtemp(prefix="post-", dir=WORK))
    after = capture(DB, SOCKET, PORT, folder)
    base, result = before["snapshot"], after["snapshot"]
    assert before["catalogue"] == after["catalogue"]
    assert all(base[key] == result[key] for key in ("columns", "constraints", "relation_owner_and_acl", "sequence_definitions"))
    tables = {name: [base["public_tables"][name][0], value[0]] for name, value in result["public_tables"].items()
              if value != base["public_tables"][name]}
    allowed = {"ir_model_fields", "ir_model_data", "ir_module_module", "ir_module_module_dependency",
               "ir_ui_view", "ir_cron_trigger"}
    if not tables.keys() <= allowed:
        raise ValueError("Unexpected changes: " + str(sorted(tables.keys() - allowed)))
    def by_id(db, table, ignored=()):
        body = "to_jsonb(t)" + "".join(" - '" + col + "'" for col in ignored)
        return json.loads(psql("SELECT json_object_agg(t.id,encode(sha256(convert_to((" + body
                               + ")::text,'UTF8')),'hex')) FROM " + table + " t", db))
    for table, ignored in [("ir_model_data", ()), ("ir_model_fields", ()), ("ir_module_module_dependency", ()), ("ir_cron_trigger", ()),
                           ("ir_module_module", ("write_date", "latest_version")), ("ir_ui_view", ("write_date",))]:
        old = by_id(HISTORY_REFERENCE, table, ignored)
        new = by_id(DB, table, ignored)
        assert old.keys() <= new.keys() and all(new[k] == v for k, v in old.items()), table
        extra = new.keys() - old.keys()
        if extra:
            checks = {"ir_model_data": "module='step_payroll_oca_sys_history'",
                      "ir_cron_trigger": "cron_id=(SELECT res_id FROM ir_model_data WHERE module='base' AND name='autovacuum_job')",
                      "ir_module_module_dependency": "name IN ('hr_expense','hr_attendance') AND module_id=(SELECT id FROM ir_module_module WHERE name='step_payroll_oca_sys_history')"}
            assert table in checks and all(k.isdecimal() for k in extra)
            assert psql("SELECT count(*) FROM " + table + " WHERE id IN (" + ",".join(extra) + ") AND NOT (" + checks[table] + ")", DB) == "0"
    versions = "SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"
    prior_versions, live = json.loads(psql(versions, HISTORY_REFERENCE)), json.loads(psql(versions, DB))
    assert len(live) == len(prior_versions) == 193 and live == dict(prior_versions, step_payroll_oca_sys_history="18.0.1.6.2")
    return {"catalogue": before["catalogue"], "tables": len(result["public_tables"]), "changed_metadata": tables,
            "advanced_sequences": sum(v != base["sequence_values"][k] for k, v in result["sequence_values"].items())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["payroll", "form", "october", "postflight"])
    parser.add_argument("references", type=Path)
    args = parser.parse_args()
    stages = {"payroll": lambda: payroll(args.references), "form": form, "october": lambda: form(args.references),
              "postflight": postflight}
    receipt = stages[args.stage]()
    (WORK / (args.stage + ".json")).write_text(json.dumps(receipt, sort_keys=True))
    print(args.stage, "verified")
