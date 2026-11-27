"""Add and repeat the two qualified document modules in the single fiscal successor using the guarded Odoo loader."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

from admit_sys_combined_documents import adopt, extract_documents
from capture_sys_combined_source import DOCUMENT_SHA, ORIGIN, ROOT, SOURCE
from custody_sys_previred_filestore import digest
from prepare_sys_fiscal_document_seed import AUX, FG, FG_RUNTIME, SOURCE_ARCHIVE
from restore_converted_sys_cohort import check_modules, full_snapshot, save, source_sequence_advances
from restore_sys_previred_pair import LOCK, require
from verify_sys_combined_product import original_policy, payroll

CHECKS = Path("/opt/steps-validation/community-sys-finance-final-checks-20261127U44FG")
DOCS = {"step_document_library": ["18.0.1.0.5", "AGPL-3"], "step_document_library_portal": ["18.0.1.0.3", "LGPL-3"]}
TREESHA = "a9622742f0e70f7de2552e1f4f1b110444191d89661ed22378890798a4319825"


def run_fiscal_shell(odoo, args, label, code):
    log = next_log(label)
    require(odoo(args, "shell", [], log, stdin=code.encode()) == 0, "fiscal-document-shell-failed:" + log.name)
    return log.read_bytes()


def next_log(label):
    idx = 0
    folder = FG_RUNTIME / "documents-review"
    folder.mkdir(exist_ok=True, mode=0o700)
    while (folder / f"{label}-{idx}.log").exists():
        idx += 1
    return folder / f"{label}-{idx}.log"


def decode(payload):
    return json.loads(next(raw.split(b"=", 1)[1] for raw in payload.splitlines() if raw.startswith(b"RESULT=")))


def exercise_original_file(odoo, args):
    accepted = json.loads((ROOT / "combined-product-proof.json").read_bytes())
    actors = AUX / "temporary-accounts.json"
    require(actors.stat().st_mode & 0o777 == 0o600, "private-portal-actors-required")
    code = "import sys,types,json,logging\nlogging.disable(logging.CRITICAL)\n"
    for name in ("probe_document_portal_http", "probe_sys_combined_document_payroll"):
        body = Path(__file__).with_name(name + ".py").read_text()
        code += f"m=types.ModuleType({name!r});sys.modules[m.__name__]=m;exec(compile({body!r},{name!r},'exec'),m.__dict__)\n"
    code += "from probe_sys_combined_document_payroll import compare_fiscal_copy\n"
    code += "actual=compare_fiscal_copy(env," + repr(json.loads(actors.read_bytes())) + "," + repr(accepted["document"]) + ")\n"
    code += "print('RESULT='+json.dumps(actual))\n"
    outcome = decode(run_fiscal_shell(odoo, args, "original-pdf", code))
    require(outcome == accepted["document"], "original-file-functional-result-drift")
    return outcome


def stage_payroll_probes():
    # The original nine scenarios remain unchanged. Five tests restrict their database
    # names to a payroll-only clone; also admit this one named combined clone in those guards.
    target = FG_RUNTIME / "qualified-payroll-probes"
    target.mkdir(exist_ok=True, mode=0o755)
    target.chmod(0o755)
    modules = ("trace_sys_rule_evaluation", "probe_sys_october_drafts", "probe_sys_payroll_book", "probe_sys_october_batch",
               "probe_sys_worked_day_reference", "probe_sys_company_drafts", "probe_sys_structure_accounting")
    hashes, scoped = {}, []
    patterns = (r"(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_COHORT_)[A-Z0-9_]+",
                r"COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]+", r"COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]{1,32}")
    for name in modules:
        src = ORIGIN / "code" / (name + ".py")
        text = src.read_text()
        raw = text
        for expr in patterns:
            guard = "re.fullmatch(r'" + expr + "',"
            if guard in text:
                require(text.count(guard) == 1, "unexpected-payroll-test-scope")
                text = text.replace(guard, "re.fullmatch(r'(?:" + expr + "|" + FG + ")',")
                scoped.append(name)
                break
        dst = target / (name + ".py")
        if not dst.exists():
            dst.write_text(text)
            dst.chmod(0o644)
        require(dst.read_text() == text, "qualified-payroll-test-file-drift")
        hashes[name] = {"source": hashlib.sha256(raw.encode()).hexdigest(), "accepted": digest(dst)}
    require(len(scoped) == 5, "unexpected-number-of-payroll-test-scope-adaptations")
    return target, hashes


def admit():
    sys.path.insert(0, str(CHECKS))
    from build_sys_upgrade_policy_profile import fingerprint
    from guard_sys_original_catalogue import checkpoint
    from rehearse_sys_module_upgrades import odoo

    require(json.loads((AUX / "pre-fiscal-seed.json").read_bytes())["all_original_rows_retained"], "qualified-seed-required")
    require((FG_RUNTIME / "document-provider-proof.json").is_file(), "fiscal-stage-must-expose-document-overlay")
    args = SimpleNamespace(database=FG, output=FG_RUNTIME, sealed=SOURCE_ARCHIVE)
    extract_documents(AUX / "documents")
    addons = AUX / "documents/addons"
    receipts = []
    for operation in ("install", "upgrade"):
        for module, expected in DOCS.items():
            label = operation + "_" + module
            saved = AUX / (label + ".json")
            if saved.exists():
                receipt = json.loads(saved.read_bytes())
                require(receipt["version"] == expected and check_modules(FG)[module] == expected, "previous-step-drift")
                receipts.append(receipt)
                continue
            require(fingerprint(addons) == (20, TREESHA), "qualified-document-tree-drift")
            pre = checkpoint(FG, label, "before")
            log = next_log(label)
            require(odoo(args, None, [], log, document_module=module, document_operation=operation) == 0 and
                    b"SYS_OFFICIAL_CLEANUP" in log.read_bytes(), "document-module-load-failed:" + log.name)
            post = checkpoint(FG, label, "after")
            require(check_modules(FG).get(module) == expected, "unexpected-document-version:" + module)
            receipt = {"module": module, "operation": operation, "version": expected, "before": pre, "after": post}
            save(saved, receipt)
            receipts.append(receipt)
        adopt(lambda code: decode(run_fiscal_shell(odoo, args, "adopt-links", code)), root=AUX, source=SOURCE, database=FG)
    modules = check_modules(FG)
    require(len(modules) == 192 and all(modules.get(k) == v for k, v in DOCS.items()), "incomplete-combined-product")
    save(AUX / "four-guarded-loads.json", {"database": FG, "module_count": len(modules), "documents_tar": DOCUMENT_SHA,
                                          "accepted_source_sha256": TREESHA, "loads": receipts})
    before = full_snapshot(FG)
    policy = original_policy(FG, AUX)
    original = exercise_original_file(odoo, args)
    save(AUX / "fg-same-file.json", original)
    probes, hashes = stage_payroll_probes()
    def execute(script):
        source = script.read_text()
        require(source.count(str(ORIGIN / "code")) == 1, "unexpected-payroll-qualification-entrypoint")
        return run_fiscal_shell(odoo, args, "payroll-finance", source.replace(str(ORIGIN / "code"), str(probes)))
    finance = payroll(before, execute)
    counters = source_sequence_advances(before, full_snapshot(FG), True)
    require(original_policy(FG, AUX) == policy, "post-workflow-policy-drift")
    final = checkpoint(FG, "combined_product_postflight", "after")
    result = {"database": FG, "source": SOURCE, "installed": len(modules), "enterprise": 0, "document": original,
              "document_release_sha256": DOCUMENT_SHA, "guarded_loads": receipts, "original_policy": policy,
              "financial": finance, "original_payroll_test_hashes": hashes, "after_functional_catalogue": final,
              "tested_tables": len(before["public_tables"]), "forward_sequences": counters}
    save(AUX / "document-admission.json", result)


if __name__ == "__main__":
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        admit()
