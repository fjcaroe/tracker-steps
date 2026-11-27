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
PROBES = {"probe_document_portal_http": "546c0bd6da4f43bb8b48f0ac3db05a59173cd90d20fa4bf06a6dca8910ee1424",
          "probe_steps_support_portal_http": "298b60e08078f79370db213596ce6860655b4b03f0f7fe9913c80b77434e3934",
          "probe_steps_support_thread": "ce0f89993cb6236ed2329d5e0d5eb270c6479f96aec7d8fffd3c1d4a37da92ea"}
PAYMENT = "COMMUNITY_STEPS_CRM_FISCAL_20261127U45F"
PAYMENT_HOME = BASE / "steps-sales-fiscal-20261127U45F"
PAYMENT_PROBES = {"probe_document_portal_http": "1920db5ba2c0e39a9932f409ea359b95a614e1455a44b599e4a0532a696470ad",
                  "probe_steps_support_portal_http": "d80543bd40f0d77d96dbdf8138422e23beb50587e7ae2010a8529dbdbcf39a64",
                  "probe_steps_support_thread": "3e1722b837999240dbab73cd998b1e38543633559e6865be2aa43f44122c1628"}


def sql_snapshot(db):
    code = ("import json,sys\nsys.path.insert(0," + repr(str(Path(__file__).resolve().parent)) + ")\n"
            "from compare_sys_full_restore import snapshot\nprint(json.dumps(snapshot(" + repr(db) +
            ",('helpdesk_ticket','ir_attachment','res_partner'))))")
    output = subprocess.check_output(["sudo", "-n", "-u", "postgres", "python3", "-B", "-"], input=code.encode())
    return json.loads(output)


def probe(phase, probe_root, payment=False):
    target, home = (PAYMENT, PAYMENT_HOME) if payment else (SUCCESSOR, INTEGRATION)
    suffix = "-payments" if payment else ""
    db, command_file = (NATIVE, NATIVE_ARGS) if phase == "reference" else (target, home / "private-args.json")
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
    if db == target:
        original = json.loads((H3 / "providers.json").read_bytes())
        original["step_helpdesk_tickets_portal"] = ["18.0.1.0.3", "LGPL-3"]
        active = check_modules(db)
        expected_count = 166 if payment else 165
        require(len(active) == expected_count and all(active.get(n) == v for n, v in original.items()) and
                active.get("step_cl_invoice_status_history") == ["18.0.1.0.3", "LGPL-3"] and
                (not payment or active.get("step_payment_in_process") == ["18.0.1.0.0", "LGPL-3"]),
                "qualified-integrated-module-graph-required")
        store = home / "data/filestore" / target
        catalog = object_catalog(attachments(target, query)["references"])
        store_snapshot = inventory(store, catalog)
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname='{db}'") == "0", "support-copy-in-use")
    parts = {}
    for name, expected in (PAYMENT_PROBES if payment else PROBES).items():
        body = (probe_root / (name + ".py")).read_bytes().replace(b"\r\n", b"\n")
        require(hashlib.sha256(body).hexdigest() == expected, "use-the-qualified-original-probe-sources")
        parts[name] = body.decode()
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
    while (OUT / (phase + suffix + "-" + str(attempt) + ".log")).exists():
        attempt += 1
    log = OUT / (phase + suffix + "-" + str(attempt) + ".log")
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
        reference_file = OUT / ("reference" + suffix + ".json")
        reference = json.loads(reference_file.read_bytes())
        require(reference["thread"] == report["thread"], "integrated-operator-content-differs")
        report["verified_http"] = compare(reference["http"], http, target=target)
        report["reference_sha256"] = hashlib.sha256(reference_file.read_bytes()).hexdigest()
    evidence_file = OUT / (phase + suffix + ".json")
    save(evidence_file, report)
    return {"phase": phase, "unchanged_tables": report["unchanged_tables"], "unchanged_sql_objects": len(ddl),
            "advanced_sequences": len(advances), "modules": report["modules"],
            "receipt_sha256": hashlib.sha256(evidence_file.read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["reference", "candidate"])
    parser.add_argument("--probe-root", type=Path, default=Path(__file__).resolve().parent,
                        help="The three native probe sources qualified at bac38850")
    parser.add_argument("--payments", action="store_true", help="Test the 166-module Steps payment and support installation")
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        print(json.dumps(probe(args.phase, args.probe_root, args.payments)))
