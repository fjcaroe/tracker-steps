"""Repeat the combined document and payroll-file workflow on its restored fiscal derivative."""
import fcntl
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

from capture_sys_combined_source import ROOT
from custody_sys_previred_filestore import digest
from restore_converted_sys_cohort import check_modules, full_snapshot, save, source_sequence_advances
from restore_native_product_backup import query
from restore_sys_previred_pair import LOCK, require
from seal_sys_combined_product import NEXT, OUTPUT

FISCAL = Path("/opt/steps-validation/community-sys-six-upgrades-20261127U44FD")
LAUNCHER = Path("/opt/steps-validation/community-sys-finance-final-checks-20261127U44FD")


def replay():
    sys.path.insert(0, str(LAUNCHER))
    from rehearse_sys_module_upgrades import odoo

    require(FISCAL.is_dir() and FISCAL.resolve() == FISCAL and (FISCAL / "profile").is_dir() and
            (FISCAL / "pinned").is_dir(), "accepted-fiscal-overlay-required")
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname='{NEXT}'") == "0", "fiscal-copy-in-use")
    modules = check_modules(NEXT)
    require(len(modules) == 192 and modules["step_document_library_portal"][0] == "18.0.1.0.3" and
            modules["step_document_library"][0] == "18.0.1.0.5" and
            modules["step_payroll_oca_sys_history"][0] == "18.0.1.6.1", "incorrect-fiscal-product")
    accepted = json.loads((ROOT / "combined-product-proof.json").read_bytes())
    source = json.loads((OUTPUT / "fiscal-source.json").read_bytes())
    require(digest(ROOT / "combined-product-proof.json") == source["source_functional_receipt_sha256"] and
            source["planned_restoration"] == NEXT, "wrong-document-functional-reference")
    actors = ROOT / "temporary-accounts.json"
    require(actors.stat().st_mode & 0o777 == 0o600, "private-portal-actors-required")
    before = full_snapshot(NEXT)
    code = "import sys,types,json,logging\nlogging.disable(logging.CRITICAL)\n"
    for name in ("probe_document_portal_http", "probe_sys_combined_document_payroll"):
        body = Path(__file__).with_name(name + ".py").read_text()
        code += f"m=types.ModuleType({name!r});sys.modules[m.__name__]=m;exec(compile({body!r},{name!r},'exec'),m.__dict__)\n"
    code += "from probe_sys_combined_document_payroll import compare_fiscal_copy\n"
    code += "actual=compare_fiscal_copy(env," + repr(json.loads(actors.read_bytes())) + "," + repr(accepted["document"]) + ")\n"
    code += "print('PORTAL_CONFIRMED='+json.dumps(actual))\n"
    args = SimpleNamespace(database=NEXT, output=FISCAL, sealed=OUTPUT / "sealed")
    idx = 0
    while (FISCAL / f"portal-original-{idx}.log").exists():
        idx += 1
    log = FISCAL / f"portal-original-{idx}.log"
    require(odoo(args, "shell", [], log, code.encode(), loopback=True) == 0, "private-fiscal-document-orm-failed")
    results = [json.loads(row.split("=", 1)[1]) for row in log.read_text().splitlines()
               if row.startswith("PORTAL_CONFIRMED=")]
    require(results == [accepted["document"]], "changed-fiscal-document-result")
    after = full_snapshot(NEXT)
    advances = source_sequence_advances(before, after, True)
    result = {"target": NEXT, "combined_source_sql_sha256": source["sql_sha256"],
              "source_functional_receipt_sha256": source["source_functional_receipt_sha256"],
              "original_document_flow_receipt": results[0], "active": len(modules), "enterprise": 0,
              "postflight_tables_unchanged": len(after["public_tables"]), "forward_sequences": advances}
    save(FISCAL / "original-document-replay.json", result)


if __name__ == "__main__":
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        replay()
