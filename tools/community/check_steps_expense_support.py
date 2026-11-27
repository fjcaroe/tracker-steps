"""Compare the full authenticated Steps helpdesk and ticket pages on the restored expense and credit-note product."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

from admit_steps_credit_note_draft import DB, ROOT, STAGE, PAYMENTS, evidence, frozen
from audit_steps_sales_schema import objects
from custody_sys_previred_filestore import digest
from restore_converted_sys_cohort import check_modules, full_snapshot, save, source_sequence_advances
from restore_sys_previred_pair import LOCK, require
sys.path.insert(0, str(STAGE/"probes"))
from verify_steps_support_portal_http import compare

ORIGINAL = "MANAGEMENT_QA_STEPS_CRM_20261126U42C"
O_ARGS = ROOT.parent/"steps-crm-20261126U42/native/private-args.json"
PROBES = ["probe_document_portal_http","probe_steps_support_thread","probe_steps_support_portal_http","probe_steps_ticket_order"]


def run(phase):
    native = phase == "native"
    db = ORIGINAL if native else DB
    file = O_ARGS if native else ROOT/"private-args.json"
    argv = json.loads(file.read_bytes())
    require(Path(__file__).resolve().parent == ROOT/"code" and argv[argv.index("-d")+1] == db and
            "--net" in argv and "--no-http" in argv and "shell" in argv and (STAGE/"compare-1.json").is_file(),
            "wrong-steps-ticket-replay")
    module_map = check_modules(DB, "hr_expense")
    parent = frozen("providers.json")
    require(module_map == {**parent, "step_expense_documents":["18.0.1.0.0","AGPL-3"],
                           "step_cl_credit_note_draft":["18.0.1.0.1","LGPL-3"]}, "incorrect-ticket-integration")
    source = {n:(STAGE/"probes"/(n+".py")).read_text() for n in PROBES}
    preamble = "import json,logging,sys,types\nlogging.disable(logging.CRITICAL)\nparts=" + repr(source) + "\n"
    program = """
for name,body in parts.items():
    mod=types.ModuleType(name)
    sys.modules[name]=mod
    exec(compile(body,name+'.py','exec'),mod.__dict__)
from probe_steps_support_thread import run as thread
from probe_steps_support_portal_http import run as http
from probe_steps_ticket_order import run as order
print('TICKET='+json.dumps({'thread':thread(env),'http':http(env),'order':order(env)},sort_keys=True))
"""
    before = full_snapshot(db, ("helpdesk_ticket","ir_attachment")) if native else evidence()
    require(digest(STAGE/"original-order.json")=="10959117c5353e17a5b02e2f279d7b3d5292d4e1fc9d3430be65ca8e86c37e1d"
            and digest(PAYMENTS/"functional-evidence.tar")==json.loads((PAYMENTS/"checkpoint.json").read_bytes())["files"]["functional-evidence.tar"][1],
            "incorrect-ticket-reference")
    initial = before if native else before["sql"]
    ddl = objects(db) if native else before["objects"]
    prefix = STAGE/("support-"+phase)
    attempt = 1
    while Path(str(prefix)+"-"+str(attempt)+".log").exists():
        attempt+=1
    log = Path(str(prefix)+"-"+str(attempt)+".log")
    with log.open("xb") as out:
        subprocess.run(argv,input=(preamble+program).encode(),stdout=out,stderr=out,check=True)
    after = full_snapshot(db, ("helpdesk_ticket","ir_attachment")) if native else evidence()
    end = after if native else after["sql"]
    advances = source_sequence_advances(initial,end,True)
    require(ddl==(objects(db) if native else after["objects"]), "ticket-replay-changed-schema")
    if not native:
        require(before["filestore"]==after["filestore"] and before["original_identities"]==after["original_identities"],
                "ticket-replay-changed-physical-storage")
    got, = [json.loads(line[7:]) for line in log.read_bytes().splitlines() if line.startswith(b"TICKET=")]
    with tarfile.open(PAYMENTS/"functional-evidence.tar") as pack:
        previous=json.load(pack.extractfile("support-original.json" if native else "support.json"))
        order = json.load(pack.extractfile("ticket-orders.json")) if not native else json.loads((STAGE/"original-order.json").read_bytes())
    require(got["thread"]==previous["thread"] and got["http"]==previous["http"]["result"] and got["order"]==order,
            "ticket-replay-differs-from-accepted-product")
    result = {"db":db,"thread":got["thread"], "http":{"db":db,"result":got["http"],"unchanged_table_rows":15,
              "probe_sha256":hashlib.sha256((preamble+program).encode()).hexdigest()}, "pagination":got["order"],
              "modules":None if native else len(module_map), "unchanged_tables":len(end["public_tables"]),
              "unchanged_sql_objects":len(ddl), "unchanged_physical_files":None if native else len(after["filestore"]),
              "forward_sequences":advances}
    if not native:
        reference = json.loads((STAGE/"support-native.json").read_bytes())
        result["verified_http"] = compare(reference["http"],result["http"],target=db)
        result["reference_sha256"] = digest(STAGE/"support-native.json")
    dest = STAGE/("support-"+phase+".json")
    save(dest,result)
    print(json.dumps({"receipt":str(dest),"sha256":digest(dest),"tables":result["unchanged_tables"]}))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("native","integrated"))
    os.umask(0o077)
    with open(LOCK,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(parser.parse_args().phase)
