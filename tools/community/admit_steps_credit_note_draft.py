"""Admit the tested draft credit-note provider in the Steps expense copy and replay the original forms."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import subprocess

from audit_steps_sales_schema import objects
from complete_converted_filestore import inventory
from credit_note_release import MODULE, compare_after, provider
from custody_sys_previred_filestore import attachments, digest, object_catalog
from load_steps_sales_extension import guarded_command
from restore_converted_sys_cohort import check_modules, full_snapshot, save, source_sequence_advances
from restore_native_product_backup import query
from restore_sys_previred_pair import LOCK, require

DB = "COMMUNITY_STEPS_EXPENSE_20261127U50E"
ROOT = Path("/opt/steps-validation/steps-expense-20261127U50E")
STAGE = ROOT / "credit-note"
PAYMENTS = ROOT.parent / "steps-sales-fiscal-20261127U45F/all-166/final-checkpoint"
PACKAGE = "5e8270b4a8bd25a91bc2bfaf4dd1db40be9be44a8bb1122449a46eaa7a03e552"
SOURCE = "183a72362efaa1fc6f9d44e946b9f7219efb0760a2b80caabb6cad611cf4c021"
NATIVE = "ef434372dc52a52df01aea2191e27d89f9c9500fd23583f8e6e04a869b2420ec"
EXPENSE = "28b5ba914b7d0a2047b8a7478889e56bc323bf7f68e1da95de9f547e7d3e7e4a"
REQUIRED_TABLES = ("hr_expense", "hr_expense_sheet", "ir_attachment")


def read(file):
    return json.loads(file.read_bytes())


def frozen(name):
    path = PAYMENTS / name
    require([path.stat().st_size,digest(path)]==read(PAYMENTS/"checkpoint.json")["files"][name], "changed-original-credit-note-source-"+name)
    return json.loads(gzip.decompress(path.read_bytes())) if name.endswith(".gz") else read(path)


def evidence():
    rows = attachments(DB,query)["references"]
    originals = object_catalog(rows)
    return {"sql": full_snapshot(DB, REQUIRED_TABLES), "objects": objects(DB),
            "filestore": inventory(ROOT/"data/filestore"/DB, originals), "original_identities": identities()}


def identities():
    return json.loads(query(DB, """SELECT jsonb_object_agg(x.module||'.'||x.name, to_jsonb(x)||jsonb_build_object(
     'target', CASE x.model WHEN 'ir.ui.view' THEN (SELECT to_jsonb(v) - 'write_uid' - 'write_date' FROM ir_ui_view v WHERE v.id=x.res_id)
                         WHEN 'ir.model.fields' THEN (SELECT to_jsonb(f) FROM ir_model_fields f WHERE f.id=x.res_id) END))
    FROM ir_model_data x WHERE x.module='l10n_cl_edi' AND (x.model='ir.ui.view' AND x.name='view_account_move_reversal'
       OR x.model='ir.model.fields' AND x.name LIKE 'field_account_move_reversal__l10n_cl_%')"""))


def run(operation):
    require(Path(__file__).resolve().parent == ROOT/"code" and ROOT.resolve(strict=True)==ROOT
            and digest(PAYMENTS/"checkpoint.json") == SOURCE and (ROOT/"expense-view-migration.json").is_file(),
            "private-expense-and-credit-note-copy-required")
    require(query("postgres", "SELECT count(*) FROM pg_stat_activity WHERE datname='"+DB+"'") == "0",
            "expense-copy-in-use")
    private = ROOT/"private-args.json"
    argv = read(private)
    require(argv[argv.index("-d")+1] == DB and "--db-filter=^"+DB+"$" in argv and "--no-http" in argv
            and "--net" in argv and "--stop-after-init" in argv and "--data-dir="+str(ROOT/"data") in argv
            and argv[argv.index("runuser"):argv.index("runuser")+4] == ["runuser","-u","odoo","--"],
            "wrong-expense-credit-note-process")
    require(digest(STAGE/"native.json")==NATIVE, "wrong-original-controls")
    active = check_modules(DB, "hr_expense")
    original_providers = frozen("providers.json")
    expense_file = ROOT/"expense-documents/admission.json"
    expense = read(expense_file)
    require(len(original_providers)==166 and expense["database"]==DB and expense["modules"]==167
            and expense["package"]==EXPENSE and expense["sql_objects"]==15183, "unqualified-expense-documents-release")
    parent = {**original_providers, "step_expense_documents": ["18.0.1.0.0","AGPL-3"]}
    combined = {**parent, MODULE:["18.0.1.0.1","LGPL-3"]}
    require(active==combined or operation=="install" and active==parent, "unqualified-expense-module-graph")
    addon = provider(STAGE/"package.tar",PACKAGE,STAGE)
    for folder in (addon, *(p for p in addon.rglob("*") if p.is_dir())):
        folder.chmod(0o755)
    index, = [i for i,arg in enumerate(argv) if arg.startswith("--addons-path=")]
    roots = [p for p in argv[index].split("=",1)[1].split(",") if p!=str(addon)]
    argv[index]="--addons-path="+",".join([str(addon),*roots])
    before=evidence()
    require(len(before["original_identities"])==5 and before["objects"]==frozen("sql-objects.json.gz")
            and before["filestore"]==frozen("filestore.json.gz"),"original-credit-note-storage-or-alias-missing")
    fixed=STAGE/"baseline.json.gz"
    if not fixed.exists():
        require(active==parent and operation=="install","unidentified-credit-note-baseline")
        original=frozen("snapshot.json.gz")
        changes=compare_after(original,before["sql"],before["objects"],before["objects"],module_load=True)
        require(set(changes)<=set(expense["changed_metadata"])|{"ir_ui_view"},
                "unexpected-expense-changes-before-credit-note")
        precursor = {**original, "public_tables": before["sql"]["public_tables"]}
        advancements = source_sequence_advances(precursor, before["sql"], True)
        initial={"providers":active,"evidence":before,"arguments_sha256":digest(private),
                 "expense_changes":changes,"expense_view_receipt":digest(ROOT/"expense-view-migration.json"),
                 "expense_documents_receipt":digest(expense_file),"expense_forward_sequences":advancements}
        with fixed.open("xb") as out:
            out.write(gzip.compress(json.dumps(initial,sort_keys=True).encode()))
    attempt=1
    while (STAGE/(operation+"-"+str(attempt)+".log")).exists():
        attempt+=1
    log=STAGE/(operation+"-"+str(attempt)+".log")
    if operation in ("install","update"):
        cmd=argv.copy()
        cmd.remove("shell")
        cmd.extend(["-i" if operation=="install" else "-u",MODULE])
        with log.open("xb") as stream:
            subprocess.run(guarded_command(cmd,ROOT,before["sql"]),stdout=stream,stderr=stream,check=True)
    else:
        code=(ROOT/"code/probe_steps_credit_note_draft.py").read_text()
        code += "\nprint('CREDIT='+json.dumps(run(env),sort_keys=True))\n"
        with log.open("xb") as stream:
            subprocess.run(argv,input=code.encode(),stdout=stream,stderr=stream,check=True)
    after=evidence()
    require(check_modules(DB,"hr_expense")==combined and after["filestore"]==before["filestore"]
            and after["original_identities"]==before["original_identities"],"expense-credit-note-originals-changed")
    delta=compare_after(before["sql"],after["sql"],before["objects"],after["objects"],module_load=operation!="compare")
    previous={**before["sql"],"public_tables":after["sql"]["public_tables"]}
    counters=source_sequence_advances(previous,after["sql"],True)
    result={"database":DB,"operation":operation,"release":PACKAGE,"providers":len(combined),"original_identities":5,
            "changed_metadata":delta,"unchanged_tables":len(after["sql"]["public_tables"])-len(delta),
            "unchanged_sql_objects":len(before["objects"]),"unchanged_physical_files":len(after["filestore"]),
            "forward_sequences":counters,"initial_baseline_sha256":digest(fixed)}
    if operation=="compare":
        rows=[r[7:] for r in log.read_bytes().splitlines() if r.startswith(b"CREDIT=")]
        require(len(rows)==1,"no-credit-note-operator-result")
        original=read(STAGE/"native.json")
        require(original["original_tables_unchanged"] and json.loads(rows[0])==original["result"],"expense-credit-notes-differ-from-native")
        report=original["result"]
        result.update(native_sha256=NATIVE,operator_comparisons=len(report["operator_invoices"]),
                      original_documents=len({r[1] for r in report["operator_invoices"]}),assigned_folios=0)
    else:
        save(private,argv)
    dest=STAGE/(operation+"-"+str(attempt)+".json")
    save(dest,result)
    print(json.dumps({"receipt":str(dest),"sha256":digest(dest),"tables":result["unchanged_tables"],"providers":len(combined)}))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation",choices=("install","update","compare"))
    o=p.parse_args()
    os.umask(0o077)
    with open(LOCK,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(o.operation)
