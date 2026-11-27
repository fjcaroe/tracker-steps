"""Compare the six original SyS negative-net settlements to the Community operator workflow."""
from pathlib import Path
import argparse
import ast
import json
import shutil
import subprocess

import prepare_sys_payslip_form_trial as trial
from prepare_sys_negative_net import DB, WORK
from check_sys_payslip_operator_form import payroll


def regression(refs):
    source=Path(__file__).resolve().parent
    dest=WORK/"probes";dest.mkdir(exist_ok=True)
    pending={"probe_sys_structure_accounting","probe_sys_company_drafts","probe_sys_october_drafts",
             "probe_sys_worked_day_reference","probe_sys_october_batch","probe_sys_payroll_book","trace_sys_rule_evaluation"}
    seen=set()
    while pending:
        name=pending.pop()
        if name in seen:continue
        seen.add(name)
        path=source/(name+".py")
        shutil.copyfile(path,dest/path.name)
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node,ast.ImportFrom) and node.module and (source/(node.module+".py")).is_file():
                pending.add(node.module)
    def runner(label,script):
        try:
            return trial.odoo(["shell"],("import sys\nsys.path.insert(0,"+repr(str(dest))+")\n"+script).encode()).stdout
        except subprocess.CalledProcessError as exc:
            (WORK/"regression-error.log").write_bytes(exc.stderr)
            raise
    result=payroll(refs,version="18.0.1.6.3",runner=runner)
    (WORK/"regression.json").write_text(json.dumps(result,sort_keys=True))


def compare(expected, observed):
    keys = ("actor","source","flags","rules","worked_types","input_uses_type_name","input_name_present","created_inputs",
            "earlier_input_edits","previous_net_matches_display","cleared_all_employee_flags",
            "flagged_periods_starting_on_or_after_draft","visible_after","state_after","journal_entry_created",
            "activities_created","activities_removed","return","new_type_from_existing_master",
            "before_action","messages_added_to_slip")
    assert expected["same_original_rows"] and observed["same_original_rows"] and len(observed["cases"])==6
    for original, candidate in zip(expected["cases"],observed["cases"],strict=True):
        mismatches=[key for key in keys if original[key]!=candidate[key]]
        if mismatches:
            raise ValueError("Negative-net outcome differs in "+str(mismatches))
        assert not candidate["journal_entry_created"] and not candidate["activities_created"]
        if candidate["before_action"]:
            assert candidate["activities_removed"]==1 and candidate["messages_added_to_slip"]==1


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("reference",type=Path)
    parser.add_argument("--regression",action="store_true");parser.add_argument("--computed",action="store_true");args=parser.parse_args()
    trial.DB,trial.WORK=DB,WORK
    if args.regression:
        regression(args.reference)
        raise SystemExit(0)
    source=Path(__file__).with_name("probe_sys_negative_net.py").read_text()
    try:
        result=trial.odoo(["shell"],(source+"\nprint('SYS '+json.dumps(effects(env, verify_first="+repr(args.computed)+")),flush=True)\n").encode())
    except subprocess.CalledProcessError as exc:
        (WORK/"negative-error.log").write_bytes(exc.stderr)
        raise
    actual,=[json.loads(line[4:]) for line in result.stdout.splitlines() if line.startswith(b"SYS ")]
    (WORK/("negative-computed.json" if args.computed else "negative.json")).write_text(json.dumps(actual,sort_keys=True))
    compare(json.loads(args.reference.read_bytes()),actual)
    print("Six original operator and deduction outcomes verified")
