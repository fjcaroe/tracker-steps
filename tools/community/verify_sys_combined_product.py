"""Check both SyS workflows on the same two-provider addition and compare the unchanged historical rows."""
import fcntl
import gzip
import hashlib
import json
import os
from collections import Counter
import subprocess

from admit_sys_combined_documents import GOLDEN, ROOT, SEALED, SOURCE, TARGET, TOOLS, command, fingerprint, shell, trigger_catalog
from capture_sys_combined_source import DOCUMENT_SHA, ORIGIN, PAYROLL_SHA
from restore_converted_sys_cohort import check_modules, full_snapshot, save, source_sequence_advances
from restore_native_product_backup import query
from restore_sys_previred_pair import LOCK, require


def original_policy():
    cutoff = json.loads((ROOT / "actors-sealed.json").read_bytes())["original_uid_cutoff"]
    result = {}
    for table in ("res_users", "res_groups", "ir_rule", "ir_model_access", "ir_attachment", "mail_mail", "documents_access"):
        highest = int(query(SOURCE, "SELECT coalesce(max(id),0) FROM " + table))
        result[table] = fingerprint(SOURCE, table)
        require(result[table] == fingerprint(TARGET, table, where=f"id<={highest}"), "historical-policy-drift:" + table)
    for table, order, where in [("res_groups_users_rel", "gid,uid", f"uid<={cutoff}"),
                                ("res_groups_implied_rel", "gid,hid", "true")]:
        result[table] = fingerprint(SOURCE, table, order, where)
        require(result[table] == fingerprint(TARGET, table, order, where), "historical-role-drift:" + table)
    result["documents_document"] = fingerprint(SOURCE, "documents_document")
    omit = ("step_original_url_hash", "step_portal_reference_hash", "step_portal_reference_prefix", "step_portal_reference_suffix")
    require(result["documents_document"] == fingerprint(TARGET, "documents_document", omit=omit), "historical-document-drift")
    require(trigger_catalog(TARGET) == trigger_catalog(SOURCE), "historical-guard-drift")
    shared = """SELECT json_build_array(count(*),count(step_original_url_hash),count(step_portal_reference_hash),
        count(*) FILTER (WHERE encode(sha256(convert_to(step_portal_reference_prefix||document_token||
        step_portal_reference_suffix,'UTF8')),'hex')=step_portal_reference_hash)) FROM documents_document"""
    require(json.loads(query(TARGET, shared)) == json.loads(query(GOLDEN, shared)) == [1430] * 4,
            "original-sharing-identity-drift")
    return result


def payroll(before):
    baseline = ORIGIN / "revision61/finance.log"
    script = ORIGIN / "revision61/finance.py"
    def financial_rows(data):
        return {line.split(b" ", 1)[0].decode(): json.loads(line.split(b" ", 1)[1])
                for line in data.splitlines() if line.startswith(b"SYSL_")}
    reference = financial_rows(baseline.read_bytes())
    require(len(reference) == 10, "reference-payroll-scenarios-missing")
    proc = subprocess.run(command(True), input=script.read_bytes(), capture_output=True)
    if proc.returncode:
        (ROOT / "payroll-error.log").write_bytes(proc.stderr)
        raise RuntimeError("private-payroll-execution-failed")
    actual = financial_rows(proc.stdout)
    require(actual.keys() == reference.keys(), "missing-combined-payroll-scenario")
    require(reference["SYSL_VERSIONS"]["installed"] == 190 and actual["SYSL_VERSIONS"]["installed"] == 192,
            "wrong-combined-module-count")
    expected = dict(reference["SYSL_VERSIONS"], installed=192)
    require(actual["SYSL_VERSIONS"] == expected, "payroll-revision-drift")
    for case in reference.keys() - {"SYSL_VERSIONS"}:
        require(actual[case] == reference[case], "payroll-result-differs:" + case)
    return {"compared_scenarios": sorted(reference.keys() - {"SYSL_VERSIONS"}), "exact_qualified_results": True,
            "reference_script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(), "validated_batch": actual["SYSL_BATCH"],
            "book_sha256": actual["SYSL_BOOK"]["csv_sha256"], "original_rules": actual["SYSL_SCOPE"]["original_rules"],
            "historical_slips": before["public_tables"]["hr_payslip"][0]}


def qualified_files():
    members = json.loads((SEALED / "runtime-members.json").read_bytes())
    qualified = {}
    for line in (SEALED / "original-release-files.sha256").read_text().splitlines():
        checksum, filename = line.split("  ", 1)
        key = filename.removeprefix("./")
        require(key not in qualified, "duplicate-qualified-payroll-member")
        qualified[key] = checksum
    modules = {key.split("/")[0] for key in qualified}
    effective = {k.removeprefix("addons/"): v[1] for k, v in members.items()
                 if k.startswith("addons/") and k.split("/")[1] in modules}
    require(effective == qualified and len(modules) == 7 and len(qualified) == 133, "qualified-payroll-tree-drift")
    script = """
import json
from pathlib import Path
from odoo.modules.module import get_manifest, get_module_path
active = env['ir.module.module'].search([('state','=','installed')])
roots = {}
for record in active:
    origin = Path(get_module_path(record.name)).resolve(strict=True)
    root = docs if record.name in ('step_document_library','step_document_library_portal') else core
    assert origin.is_relative_to(root) and get_manifest(record.name)['license'] == record.license
    roots[record.name] = get_manifest(record.name)['license']
print('RESULT='+json.dumps(roots))
env.cr.rollback()
"""
    defs = "from pathlib import Path\ncore=Path(" + repr(str(SEALED / "runtime")) + ")\ndocs=Path(" + repr(str(ROOT / "documents/addons")) + ")\n"
    resolved = shell(defs + script)
    require(len(resolved) == 192, "combined-effective-provider-set-drift")
    return {"qualified_payroll_members": len(qualified), "exact_payroll_modules": len(modules),
            "effective_providers": len(resolved), "effective_licenses": dict(Counter(resolved.values()))}


def verify():
    require(json.loads((ROOT / "combined-admission.json").read_bytes())["package_sha256"] == DOCUMENT_SHA,
            "documents-not-admitted")
    sources = qualified_files()
    before = full_snapshot(TARGET)
    original = json.loads(gzip.decompress((SEALED / "source-snapshot.json.gz").read_bytes()))
    payroll_tables = {name: record for name, record in original["public_tables"].items()
                      if name.startswith(("hr_payslip", "hr_contract", "hr_salary_", "hr_payroll_", "account_move"))}
    require(len(payroll_tables) >= 20 and before["public_tables"]["hr_payslip"][0] == 765 and
            all(before["public_tables"].get(name) == value for name, value in payroll_tables.items()), "historical-payroll-drift")
    policy = original_policy()
    prepared = json.loads((ROOT / "temporary-accounts.json").read_bytes())
    require(len(prepared) == 2, "two-portal-fixtures-required")
    setup = "import sys,logging,json\nlogging.disable(logging.CRITICAL)\nsys.path.insert(0," + repr(str(TOOLS)) + ")\n"
    code = setup + "from probe_sys_combined_document_payroll import combined\nprint('RESULT='+json.dumps(combined(env," + repr(prepared) + ")))\n"
    common = shell(code)
    save(ROOT / "combined-same-file.json", common)
    financial = payroll(before)
    after = full_snapshot(TARGET)
    advances = source_sequence_advances(before, after, True)
    require(original_policy() == policy, "changed-policy-after-functional-replay")
    modules = check_modules(TARGET)
    licenses = dict(Counter(record[1] for record in modules.values()))
    source_proof = json.loads((SEALED / 'backup.json').read_bytes())
    require(licenses == {'AGPL-3': 2, 'LGPL-3': 190} and source_proof['effective_licenses'] == {'AGPL-3': 1, 'LGPL-3': 189},
            'unexpected-license-profile')
    require(len(modules) == 192 and modules["step_payroll_oca_sys_history"][0] == "18.0.1.6.1" and
            modules["step_document_library"][0] == "18.0.1.0.5" and
            modules["step_document_library_portal"][0] == "18.0.1.0.3", "combined-profile-drift")
    save(ROOT / "combined-product-proof.json", {"source": SOURCE, "target": TARGET, "installed": len(modules),
         "enterprise": 0, "licenses": licenses, "resolved_packages": sources, "payroll_release_sha256": PAYROLL_SHA, "document_release_sha256": DOCUMENT_SHA,
         "payroll": financial, "document": common, "guard_count": len(trigger_catalog(TARGET)),
         "original_policy": policy, "preserved_payroll_tables": len(payroll_tables),
         "all_target_tables_unchanged_after_tests": len(after["public_tables"]), "forward_sequences": advances})


if __name__ == "__main__":
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        verify()
