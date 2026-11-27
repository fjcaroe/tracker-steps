"""Install a sealed Steps draft credit-note extension in the disposable U46D database and compare its two workflows."""
import argparse
import fcntl
import json
from pathlib import Path
import shutil
import subprocess

from load_steps_sales_extension import guarded_command
import restore_local_steps_integrated as local
from verify_converted_backup import check, hash_file, read_json

from credit_note_release import MODULE, provider, compare_after


DATABASE = "COMMUNITY_STEPS_CRM_PAYMENTS_TEST_20261127U46D"


def run(operation, archive, checksum, native):
    root = local.MEM / "payment-recovery"
    trial = root / "payment-rehearsal"
    check(read_json(trial/"identity.json")["database"] == DATABASE, "wrong-credit-note-trial")
    stage = trial / ("credit-" + checksum)
    local.checked_directory(stage,0o755)
    overlay = provider(archive, checksum, stage)
    code = stage / "code"
    local.checked_directory(code,0o755)
    for name in ("load_steps_sales_extension.py","preflight_original_history_storage.py"):
        shutil.copyfile(local.TOOLS/name,code/name)
        (code/name).chmod(0o644)
    cmd = local.shell_command(DATABASE, trial, root/"addons")
    pos, = [i for i,arg in enumerate(cmd) if arg.startswith("--addons-path=")]
    cmd[pos] = "--addons-path=" + str(overlay) + "," + cmd[pos].split("=",1)[1]
    local.cluster()
    try:
        before, ddl = local.snapshot(DATABASE)
        if operation in ("install","update"):
            cmd.remove("shell")
            cmd += ["--stop-after-init", "-i" if operation == "install" else "-u", MODULE]
            cmd = guarded_command(cmd, stage, before)
            with (stage / (operation + ".log")).open("ab") as log:
                local.call("odoo", cmd, stdout=log, stderr=log)
        else:
            source = (local.TOOLS/"probe_steps_credit_note_draft.py").read_text()
            source += "\nprint('CREDIT='+json.dumps(run(env),sort_keys=True))\n"
            with (stage/"operator.log").open("wb") as log:
                local.call("odoo", cmd, input=source.encode(), stdout=log, stderr=log)
        after, after_ddl = local.snapshot(DATABASE)
        delta = compare_after(before,after,ddl,after_ddl,module_load=operation != "compare")
        version = local.query(DATABASE, "SELECT state||'/'||latest_version FROM ir_module_module WHERE name='"+MODULE+"'")
        check(version == "installed/18.0.1.0.1", "credit-note-module-not-installed")
        count = int(local.query(DATABASE, "SELECT count(*) FROM ir_module_module WHERE state='installed'"))
        check(count == 167, "wrong-credit-note-provider-count")
        result = {"database": DATABASE, "operation": operation, "module": MODULE, "providers":count,"release": checksum,
                  "version":version, "unchanged_tables":len(after["public_tables"])-len(delta),
                  "changed_metadata":delta, "sql_objects":len(after_ddl)}
        if operation == "compare":
            rows = [line[7:] for line in (stage/"operator.log").read_bytes().splitlines() if line.startswith(b"CREDIT=")]
            check(len(rows) == 1,"credit-note-operator-probe-failed")
            actual = json.loads(rows[0])
            ref = read_json(native)
            (stage/"draft-results.json").write_text(json.dumps(actual,sort_keys=True))
            check(ref["original_tables_unchanged"] and actual == ref["result"], "credit-note-differs-from-original")
            result["original_workflows_sha256"] = hash_file(native)
            result["ordinary"] = actual["default"]["references"][0]["code"]
            result["text_correction"] = actual["text_correction"]["references"][0]["code"]
            result["assigned_folios"] = sum(actual[name]["folio_assigned"] for name in ("default","text_correction","blank_text"))
            result["operator_invoice_comparisons"] = len(actual["operator_invoices"])
        destination = stage / (operation + "-result.json")
        destination.write_text(json.dumps(result,sort_keys=True,indent=2))
        print(json.dumps(result))
    finally:
        local.call("postgres",["pg_ctl","-D",str(local.MEM/"postgres/cluster"),"-m","fast","-w","stop"],stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("install","update","compare"))
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--native", type=Path, required=True)
    a=parser.parse_args()
    with open("/dev/shm/steps-shared-qa-restore.lock","a+b") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(a.operation,a.archive,a.sha256,a.native)
