"""Exercise the restored final SyS product with genuine operator scopes and native receipts."""
import argparse
import ast
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from compare_sys_company_drafts import compare as compare_payroll
from compare_sys_payroll_exports_all import compare as compare_exports
from seal_local_sys_193 import CODE, DB, MEM, PORT, ROOT, SOCKET, capture, providers, save, sha

TOOLS = Path(__file__).resolve().parent
FROZEN_FINANCE = "59f3bade54e5c6d72e77d803beed643be9122d42687634f58de9ecff44335938"
FROZEN_LOG = "cedf81f5d3f40677cb978aeb69812b54cae2a0c50af409268dcede50a9450160"
SETUP = "import json,sys,secrets\nfrom pathlib import Path\nsys.path.insert(0," + repr(str(CODE)) + ")\nassert env.cr.dbname==" + repr(DB) + "\n"
FINAL = MEM / "proofs"
ROOTS = ("probe_sys_structure_accounting", "probe_sys_company_drafts", "probe_sys_october_drafts",
         "probe_sys_worked_day_reference", "probe_sys_october_batch", "probe_sys_payroll_book",
         "trace_sys_rule_evaluation", "probe_sys_payroll_exports_all", "probe_sys_combined_document_payroll",
         "probe_converted_cohort_attachment", "probe_sys_invoice_pdf", "original_report_loopback")


def prepare(custody, refs):
    if not (FINAL / "restored.json").is_file():
        raise ValueError("A verified full independent restoration is required")
    CODE.mkdir(mode=0o755, exist_ok=True)
    todo = set(ROOTS)
    copied = set()
    while todo:
        name = todo.pop()
        if name in copied:
            continue
        src = TOOLS / (name + ".py")
        shutil.copyfile(src, CODE / src.name)
        copied.add(name)
        for node in ast.walk(ast.parse(src.read_bytes())):
            if isinstance(node, ast.ImportFrom) and node.module and (TOOLS / (node.module + ".py")).is_file():
                todo.add(node.module)
    finance = refs / "U43C/wsl-finance-reference"
    if sha(finance / "finance.py") != FROZEN_FINANCE or sha(finance / "finance.log") != FROZEN_LOG:
        raise ValueError("Changed reference finance scenarios")
    (MEM / "odoo.conf").write_text("[options]\ndb_user = odoo\nlist_db = False\nlog_level = warn\n"
                                   "db_host = " + SOCKET + "\ndb_port = " + str(PORT) + "\n")
    with (MEM / "expected.json").open("w") as out:
        json.dump(providers(custody), out, sort_keys=True)
    doc = json.loads((custody / "document-admission.json").read_bytes())["document"]
    role = json.loads((refs / "U43C/fiscal-payroll-documents-recovery/verified-recovery.json").read_bytes())["role_probe"]
    save(MEM / "original-documents.json", {"document": doc, "role": role})
    return finance


def shell(stage, script, *, loopback=False):
    command = ["python3.10", "/work/sys-fg-code/odoo-bin", "shell", "-c", str(MEM / "odoo.conf"),
               "-d", DB, "--db-filter=^" + DB + "$", "--data-dir=" + str(MEM / "data"),
               "--addons-path=" + str(MEM / "overlay") + ",/work/sys-fg-code/addons,/work/sys-fg-code/odoo/addons",
               "--load=base,web", "--no-http", "--workers=0", "--max-cron-threads=0", "--stop-after-init", "--without-demo=all"]
    if loopback:
        command = ["python3.10", str(CODE / "original_report_loopback.py"), "--service-process", *command]
    os.umask(0o077)
    runner = [sys.executable, str(TOOLS / "run_focal_print_command.py"), "--user", "odoo"]
    if loopback:
        runner.append("--loopback")
    with (FINAL / (stage + ".stderr")).open("wb") as error:
        proc = subprocess.run([*runner, "--", *command], input=(SETUP + script).encode(), stdout=subprocess.PIPE, stderr=error)
    (FINAL / (stage + ".stdout")).write_bytes(proc.stdout)
    if proc.returncode:
        raise RuntimeError(stage + " failed. See private traceback: " + str(FINAL / (stage + ".stderr")))
    return proc.stdout


def registry():
    script = """
from odoo.modules.module import get_module_path,get_manifest
expected=json.loads(Path('/dev/shm/sys-fg-193/expected.json').read_bytes())
env.cr.rollback()
env.cr.execute('SET TRANSACTION READ ONLY')
live=env['ir.module.module'].search([('state','=','installed')])
assert len(live)==len(expected)==193 and all([m.latest_version,m.license]==expected[m.name] for m in live)
assert all(m.license in ('AGPL-3','LGPL-3') for m in live)
for m in live:
    provider=Path(get_module_path(m.name)).resolve()
    if m.name=='step_report_print_colors':
        assert provider==Path('/dev/shm/sys-fg-193/overlay')/m.name
    else:
        assert provider.is_relative_to('/work/sys-fg-code')
    assert get_manifest(m.name)['version']==m.latest_version
print('SYS '+json.dumps({'active':len(live),'effective_versions':True}),flush=True)
"""
    return result(shell("registry", script))


def result(raw):
    found = [json.loads(line[4:]) for line in raw.splitlines() if line.startswith(b"SYS ")]
    if len(found) != 1:
        raise ValueError("One runtime receipt required")
    return found[0]


def payroll(finance, refs):
    actual_raw = shell("payroll", (finance/"finance.py").read_text())
    def entries(data):
        pairs = [line.split(b" ", 1) for line in data.splitlines() if line.startswith(b"SYSL_")]
        return {name.decode(): json.loads(body) for name, body in pairs}
    original = entries((finance/"finance.log").read_bytes())
    actual = entries(actual_raw)
    if len(original) != 10 or actual.keys() != original.keys() or actual["SYSL_VERSIONS"] != dict(original["SYSL_VERSIONS"], installed=193):
        raise ValueError("Qualified module versions or scenarios differ")
    for case in actual.keys() - {"SYSL_VERSIONS"}:
        if actual[case] != original[case]:
            raise ValueError("Original financial behavior differs: " + case)
    native = json.loads((refs/"U40/U40R17POSTALL-native-companies.json").read_bytes())
    rows = compare_payroll(native, actual["SYSL_COMPANIES"], accounting=True, require_review_policy=True)
    total = sum(rows.values(), Counter())
    if (len(rows), total["selected"], total["same_calculation"], total["both_rejected"], total["matching_confirmations"]) != (12,133,130,3,130):
        raise ValueError("The 133 original salary or accounting results differ")
    return {"companies":len(rows), "results": dict(total), "scenarios": sorted(actual.keys()-{'SYSL_VERSIONS'}),
            "matches_reference":True, "book_sha256":actual["SYSL_BOOK"]["csv_sha256"]}


def documents():
    script = """
from probe_sys_combined_document_payroll import combined
from probe_converted_cohort_attachment import restricted_attachment,original_library_payslip
ref=json.loads(Path('/dev/shm/sys-fg-193/original-documents.json').read_bytes())
role=ref['role']; actor=env['res.users'].browse(role['internal_uid'])
env.cr.rollback();env.cr.execute('SET TRANSACTION READ ONLY')
pdf=restricted_attachment(env,actor)
record=ref['document']; expected=[record[k] for k in ('payslip','document','attachment','bytes','same_pdf_sha256')]
linked=original_library_payslip(env,actor,expected)
assert pdf==role['payroll_pdf'] and linked==role['original_library_payslip']
env.cr.rollback();env.invalidate_all(flush=False)
people=env['res.users'].search([('login','=like','community-portal-%'),('active','=',True),('share','=',True)],order='id')
assert len(people)==2
prepared=[(u.id,u.login,secrets.token_urlsafe(32)) for u in people]
now=combined(env,prepared,transactional_passwords=True)
assert now==record
print('SYS '+json.dumps({'document':now,'two_historical_files':True}),flush=True)
"""
    return result(shell("documents", script))


def exports(refs):
    script = """
from probe_sys_payroll_exports_all import run
key=Path('/dev/shm/sys-fg-193/export-comparison.key').read_bytes()
print('SYS '+json.dumps(run(env,key)),flush=True)
"""
    actual = result(shell("exports", script))
    native = json.loads((refs/"U40H/U41X3-native.json").read_bytes())
    compare = compare_exports(native, actual)
    if not compare["complete_match"] or compare["operator_company_pairs"] != 24 or not actual["originals_preserved"]:
        raise ValueError("One original export, refusal, permission or diagnostic differs")
    return {"companies":compare["companies"],"pairs":compare["operator_company_pairs"],"periods":compare["closed_by_period"],
            "results":compare["results"],"complete_match":True}


def financial_pdfs():
    return result(shell("invoices", "from probe_sys_invoice_pdf import run\nprint('SYS '+json.dumps(run(env)),flush=True)\n", loopback=True))


def generated_cache():
    from seal_local_sys_193 import SOURCE, pg, psql
    # Re-extracting stylesheets can change the cache URL even when the emitted CSS is byte-identical.
    sql = """SELECT json_object_agg(id,encode(sha256(convert_to(to_jsonb(a)::text,'UTF8')),'hex'))
             FROM ir_attachment a"""
    def original(q):
        return json.loads(pg("psql","-XtA","-d",SOURCE,"-c",q,capture_output=True).stdout)
    previous, current = original(sql), json.loads(psql(sql))
    if len(previous) != 5441 or len(current) != 5441 or any(previous[k] != current[k] for k in previous.keys() & current.keys()):
        raise ValueError("Original attachment row changed")
    missing, added = sorted(previous.keys()-current.keys()), sorted(current.keys()-previous.keys())
    if not missing and not added:
        return {"original_rows_retained":5441,"new_urls":0}
    if len(missing) != 1 or len(added) != 1 or not all(k.isdecimal() for k in missing+added):
        raise ValueError("Unexpected number of replaced attachments")
    fields = """SELECT json_build_array(name,mimetype,res_model,res_id,store_fname,checksum,file_size)
                FROM ir_attachment WHERE id="""
    old, new = original(fields+missing[0]), json.loads(psql(fields+added[0]))
    if old != new or old[:4] != ["web.report_assets_common.min.css","text/css","ir.ui.view",0]:
        raise ValueError("Reissued cache is not the same generated stylesheet")
    return {"original_rows_retained":5440,"new_urls":1,"identical_css_sha1":new[5],"identical_css_bytes":new[6]}


def final(custody):
    from seal_local_sys_193 import SOURCE, STORE, inventory
    baseline = json.loads(gzip.decompress((MEM / "sealed/snapshot.json.gz").read_bytes()))
    observed = capture(DB, SOCKET, PORT, FINAL / "post")
    if observed["catalogue"] != baseline["catalogue"]:
        raise ValueError("Schema changed during functional proofs")
    current, original = observed["snapshot"], baseline["snapshot"]
    caches=generated_cache()
    for name,row in original["public_tables"].items():
        if name != "ir_attachment" and current["public_tables"].get(name) != row:
            raise ValueError("Persisted original rows changed in " + name)
    if original["public_tables"].keys() != current["public_tables"].keys():
        raise ValueError("Public table inventory changed")
    for section in original.keys() - {"sequence_values","public_tables"}:
        if current[section] != original[section]:
            raise ValueError("Persisted original state changed: " + section)
    before, after = original["sequence_values"], current["sequence_values"]
    changed = {n: [a,after[n]] for n,a in before.items() if a != after[n]}
    if after.keys() != before.keys() or any(b[0] < a[0] or not b[1] for a,b in changed.values()):
        raise ValueError("Sequence rewind")
    frozen_files = json.loads(gzip.decompress((MEM/"sealed/filestore.json.gz").read_bytes()))
    if inventory(MEM/"data/filestore"/DB) != frozen_files:
        raise ValueError("Original physical files changed")
    source_proof = FINAL / "source-post"
    source_proof.mkdir(exist_ok=True)
    if capture(SOURCE, "/run/sys-55441", 55441, source_proof) != baseline or inventory(STORE) != frozen_files:
        raise ValueError("The sealed source changed during the independent restoration or exercises")
    for name in ("registry","payroll","exports","documents","invoices"):
        if not (FINAL/(name+".json")).is_file():
            raise ValueError("Missing completed flow: "+name)
    return {"release":sha(MEM/"sealed/release.json"),"complete":True,"rows":sum(v[0] for v in current["public_tables"].values()),
            "tables":len(current["public_tables"]),"file_count":len(frozen_files),"advanced_sequences":changed,
            "generated_report_cache":caches,"unchanged_business_data":True,"original_counters_at_recovery":len(before),"source_control_unchanged":True}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=("registry","payroll","documents","exports","invoices","final"))
    p.add_argument("custody",type=Path)
    p.add_argument("references",type=Path)
    a=p.parse_args()
    if a.stage=="final":
        (FINAL/"post").mkdir(exist_ok=True)
    finance=prepare(a.custody,a.references)
    tasks={"registry":registry,"payroll":lambda:payroll(finance,a.references),"documents":documents,
           "exports":lambda:exports(a.references),"invoices":financial_pdfs,"final":lambda:final(a.custody)}
    outcome=tasks[a.stage]()
    save(FINAL/(a.stage+".json"),outcome)
    print(a.stage, sha(FINAL/(a.stage+".json")))
