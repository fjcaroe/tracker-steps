"""Replay authenticated support pages and the original users' chatter on the integrated private Steps fiscal copy."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess

from audit_steps_sales_schema import objects
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, object_catalog
from restore_converted_sys_cohort import check_modules, save, source_sequence_advances
from restore_native_product_backup import query
from restore_steps_support_backup import OUTPUT as INTEGRATION
from restore_sys_previred_pair import LOCK, require
from verify_steps_support_backup import ACCEPTANCE, SOURCE, SUCCESSOR
from verify_steps_support_portal_http import compare


NATIVE = "MANAGEMENT_QA_STEPS_CRM_20261126U42C"
BASE = Path("/opt/steps-validation")
OUT = BASE / "steps-integrated-support-check-20261127U46A"
H3 = BASE / "steps-sales-support-20261127U44H3/final-checkpoint"
NATIVE_ARGS = BASE / "steps-crm-20261126U42/native/private-args.json"


def sql_snapshot(db):
    code = ("import json,sys\nsys.path.insert(0," + repr(str(Path(__file__).resolve().parent)) + ")\n"
            "from compare_sys_full_restore import snapshot\nprint(json.dumps(snapshot(" + repr(db) +
            ",('helpdesk_ticket','ir_attachment','res_partner'))))")
    output = subprocess.check_output(["sudo", "-n", "-u", "postgres", "python3", "-B", "-"], input=code.encode())
    return json.loads(output)


def probe(phase):
    db, command_file = (NATIVE, NATIVE_ARGS) if phase == "reference" else (SUCCESSOR, INTEGRATION / "private-args.json")
    require(OUT.resolve(strict=True) == OUT, "private-support-output-required")
    args = json.loads(command_file.read_bytes())
    require(args[args.index("-d") + 1] == db and "--no-http" in args and "--net" in args, "private-targeted-shell-required")
    old = (H3 / "acceptance.json").read_bytes()
    require(hashlib.sha256(old).hexdigest() == ACCEPTANCE, "H3-functional-reference-drift")
    previous = (OUT / "accepted-native-http.json").read_bytes()
    require(hashlib.sha256(previous).hexdigest() == json.loads(old)["receipts_sha256"]["native-http"],
            "unrecognized-native-ticket-reference")
    active = None
    store_snapshot = None
    if db == SUCCESSOR:
        original = json.loads((H3 / "providers.json").read_bytes())
        active = check_modules(db)
        require(len(active) == 165 and all(active.get(n) == v for n, v in original.items()) and
                "step_cl_invoice_status_history" in active, "qualified-165-module-candidate-required")
        store = INTEGRATION / "data/filestore" / SUCCESSOR
        catalog = object_catalog(attachments(SUCCESSOR, query)["references"])
        store_snapshot = inventory(store, catalog)
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname='{db}'") == "0", "support-copy-in-use")
    parts = {}
    for name in ("probe_document_portal_http", "probe_steps_support_portal_http", "probe_steps_support_thread"):
        parts[name] = Path(__file__).with_name(name + ".py").read_text()
    code = """
import json, logging, sys, types
logging.disable(logging.CRITICAL)
parts = _parts
for name, body in parts.items():
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(body, name + '.py', 'exec'), module.__dict__)
from probe_steps_support_thread import run as check_thread
from probe_steps_support_portal_http import run as check_http
print('RESULT=' + json.dumps({'thread':check_thread(env),'http':check_http(env)},sort_keys=True))
"""
    sha = hashlib.sha256((json.dumps(parts, sort_keys=True) + code).encode()).hexdigest()
    snap, ddl = sql_snapshot(db), objects(db)
    attempt = 1
    while (OUT / (phase + "-" + str(attempt) + ".log")).exists():
        attempt += 1
    log = OUT / (phase + "-" + str(attempt) + ".log")
    with log.open("xb") as handle:
        subprocess.run(args, input=("_parts=" + repr(parts) + "\n" + code).encode(), stdout=handle, stderr=handle, check=True)
    current = sql_snapshot(db)
    advances = source_sequence_advances(snap, current, True)
    require(ddl == objects(db), "support-probe-changed-SQL-objects")
    if store_snapshot is not None:
        require(check_modules(db) == active and inventory(store, catalog) == store_snapshot,
                "support-probe-changed-modules-or-physical-files")
    (result,) = [json.loads(row[7:]) for row in log.read_bytes().splitlines() if row.startswith(b"RESULT=")]
    require(result["http"] == json.loads(previous)["result"] and result["thread"]["operators"] ==
            [json.loads(old)["original_chatter"]] * 2, "qualified-support-result-differs")
    http = {"db": db, "probe_sha256": sha, "unchanged_table_rows": 15, "result": result["http"]}
    report = {"db": db, "http": http, "thread": result["thread"], "unchanged_tables": len(current["public_tables"]),
              "unchanged_sql_objects": len(ddl), "forward_sequences": advances,
              "unchanged_physical_files": len(store_snapshot) if store_snapshot is not None else None,
              "modules": len(active) if active else None, "H3": SOURCE, "H3_acceptance_sha256": ACCEPTANCE}
    if phase == "candidate":
        reference = json.loads((OUT / "reference.json").read_bytes())
        require(reference["thread"] == report["thread"], "integrated-operator-content-differs")
        report["verified_http"] = compare(reference["http"], http, target=SUCCESSOR)
        report["reference_sha256"] = hashlib.sha256((OUT / "reference.json").read_bytes()).hexdigest()
    save(OUT / (phase + ".json"), report)
    return {"phase": phase, "unchanged_tables": report["unchanged_tables"], "unchanged_sql_objects": len(ddl),
            "advanced_sequences": len(advances), "modules": report["modules"],
            "receipt_sha256": hashlib.sha256((OUT / (phase + ".json")).read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["reference", "candidate"])
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        print(json.dumps(probe(args.phase)))
