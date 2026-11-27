"""Qualify the stable responsible-user tie break on the 165-module private Steps product."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import subprocess
import tarfile

from audit_steps_sales_schema import objects
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from load_steps_sales_extension import guarded_command
from restore_converted_sys_cohort import check_modules, full_snapshot, save, source_sequence_advances
from restore_native_product_backup import query
from restore_steps_support_backup import OUTPUT as WORK
from restore_sys_previred_pair import LOCK, require
from verify_steps_support_backup import PACKAGES, SUCCESSOR, canonical, strong


PORTAL = "step_helpdesk_tickets_portal"
RELEASE = "23d61b9f8c3ed1f4e9c59f238fe38b8ff45d75b41c3035acd1dac1fc7920d68a"
EXPERIMENT = "10959117c5353e17a5b02e2f279d7b3d5292d4e1fc9d3430be65ca8e86c37e1d"
STAGE = WORK / ("support-portal-" + RELEASE[:12])
BASELINE = STAGE / "baseline.json.gz"


def physical():
    rows = attachments(SUCCESSOR, query)
    store = inventory(WORK / "data/filestore" / SUCCESSOR, object_catalog(rows.pop("references")))
    return [rows, strong(store), len(store)]


def payload():
    archive = STAGE / "portal.tar"
    require(digest(archive) == RELEASE and digest(STAGE / "native-orders.json") == EXPERIMENT, "unknown-portal-package")
    base = WORK / "addons" / PORTAL
    approved = WORK.parent / "steps-sales-support-20261127U44H3/final-checkpoint" / (PORTAL + ".tar")
    require(digest(approved) == PACKAGES[PORTAL][0], "old-portal-package-missing")
    with tarfile.open(approved) as original, tarfile.open(archive) as updated:
        old = {m.name: original.extractfile(m).read() for m in original if m.isfile()}
        new = {m.name: updated.extractfile(m).read() for m in updated if m.isfile()}
    require(old.keys() == new.keys() and len(old) == 7 and all((base.parent / name).read_bytes() == data
            for name, data in old.items()), "unexpected-previous-portal-bytes")
    changed = {key for key in old if old[key] != new[key]}
    require(changed == {PORTAL + "/__manifest__.py", PORTAL + "/controllers/portal.py"}, "unexpected-release-change")
    dest = STAGE / "addons"
    for name, data in new.items():
        path = dest / name
        require(path.resolve() == path and path.is_relative_to(dest / PORTAL), "unknown-portal-target")
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if not path.exists():
            with path.open("xb") as out:
                out.write(data)
        require(path.read_bytes() == data, "new-portal-release-drift")
        path.chmod(0o644)
    for folder in [dest, *(p for p in dest.rglob("*") if p.is_dir())]:
        folder.chmod(0o755)
    require({p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()} == new.keys(), "extra-portal-code")
    return dest


def run(phase):
    require(STAGE.resolve(strict=True) == STAGE and Path(__file__).resolve().parent == STAGE / "code",
            "private-portal-guard-required")
    active = check_modules(SUCCESSOR)
    require(len(active) == 165 and active["step_cl_invoice_status_history"] == ["18.0.1.0.3", "LGPL-3"]
            and active[PORTAL][0] in ("18.0.1.0.2", "18.0.1.0.3"), "unknown-combined-product")
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname='{SUCCESSOR}'") == "0",
            "integrated-copy-in-use")
    addon = payload()
    if not BASELINE.exists():
        require(phase == "preflight" and active[PORTAL][0] == "18.0.1.0.2", "explicit-qualified-preflight-required")
        data = {"db": SUCCESSOR, "modules": active, "snapshot": full_snapshot(SUCCESSOR),
                "sql_objects": objects(SUCCESSOR), "store": physical(), "portal_before": PACKAGES[PORTAL][0]}
        BASELINE.write_bytes(gzip.compress(canonical(data), mtime=0))
    frozen = json.loads(gzip.decompress(BASELINE.read_bytes()))
    snapshot = full_snapshot(SUCCESSOR)
    require(objects(SUCCESSOR) == frozen["sql_objects"] and physical() == frozen["store"], "protected-H3-storage-differs")
    if phase == "preflight":
        require(frozen["snapshot"] == snapshot and frozen["modules"] == active, "portal-preflight-changed")
        result = {"phase": phase, "database": SUCCESSOR, "modules": len(active), "baseline_sha256": digest(BASELINE),
                  "previous": PACKAGES[PORTAL][0], "package": RELEASE, "native_order_proof": EXPERIMENT,
                  "objects": len(frozen["sql_objects"]), "tables": len(snapshot["public_tables"]), "physical_files": frozen["store"][2]}
    else:
        wanted = "18.0.1.0.2" if phase == "upgrade" else "18.0.1.0.3"
        require(active[PORTAL][0] == wanted, "unexpected-initial-module-version")
        argv = json.loads((WORK / "private-args.json").read_bytes())
        pos, = [i for i, x in enumerate(argv) if x.startswith("--addons-path=")]
        roots = argv[pos].split("=", 1)[1].split(",")
        old_roots = [str(p) for p in (WORK / "fiscal-addons", WORK / "addons", WORK / "runtime/addons", WORK / "runtime/odoo/addons")]
        require(roots in (old_roots, [str(addon), *old_roots]), "unknown-integrated-addon-profile")
        argv[pos] = "--addons-path=" + ",".join([str(addon), *old_roots])
        direct = [s for s in argv if s != "shell"] + ["-u", PORTAL]
        with (STAGE / (phase + ".log")).open("ab") as log:
            subprocess.run(guarded_command(direct, STAGE, frozen["snapshot"]), stdout=log, stderr=log, check=True)
        after = full_snapshot(SUCCESSOR)
        protected = {n for n in after if n not in ("sequence_values", "public_tables")}
        require(all(after[n] == frozen["snapshot"][n] for n in protected) and
                objects(SUCCESSOR) == frozen["sql_objects"] and physical() == frozen["store"], "SQL-or-file-storage-changed")
        initial = frozen["snapshot"]["public_tables"]
        require(initial.keys() == after["public_tables"].keys(), "table-inventory-changed")
        changes = sorted(n for n in initial if initial[n] != after["public_tables"][n])
        require(set(changes) <= {"ir_module_module", "ir_model_data", "ir_ui_view", "ir_module_module_dependency",
                                "ir_model", "ir_model_fields", "ir_model_fields_selection", "ir_cron_trigger"},
                "unrelated-change-after-portal-upgrade:" + repr(changes))
        final = check_modules(SUCCESSOR)
        require(final == {**frozen["modules"], PORTAL: ["18.0.1.0.3", "LGPL-3"]}, "non-portal-module-changed")
        projected = {**frozen["snapshot"], "public_tables": after["public_tables"]}
        advances = source_sequence_advances(projected, after, True)
        save(WORK / "private-args.json", argv)
        result = {"phase": phase, "database": SUCCESSOR, "modules": len(final), "baseline_sha256": digest(BASELINE),
                  "previous": PACKAGES[PORTAL][0], "package": RELEASE, "native_order_proof": EXPERIMENT,
                  "changed_metadata": changes, "objects": len(frozen["sql_objects"]),
                  "unchanged_tables": len(initial) - len(changes), "sequences_advanced": len(advances), "physical_files": frozen["store"][2]}
    save(STAGE / (phase + ".json"), result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["preflight", "upgrade", "repeat"])
    params = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        print(json.dumps(run(params.phase)))
