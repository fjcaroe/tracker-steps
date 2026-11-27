"""Compare the original 33 SyS October calculation changes in a disposable restoration and the native QA copy."""

from collections import Counter
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

from complete_converted_filestore import inventory, restore_supplement
from compare_sys_summary_variance import classify
from custody_sys_previred_filestore import attachments, digest, object_catalog
from rehearse_sys_module_upgrades import differences, guards, module_versions, odoo, restore, save, snapshot
from restore_native_product_backup import query
from restore_sys_previred_pair import LOCK, require


CODE = Path(__file__).resolve().parent
PRIVATE = Path("/opt/steps-validation")
BASE = PRIVATE / "community-sys-payroll-document-20261127U43C/sealed"
ORIGINAL = "MANAGEMENT_QA_SYS_PREVIRED_20261126U40N"
DB = "COMMUNITY_SYS_PREVIRED_MODULES_20261127U44VA"
ROOT = PRIVATE / "community-sys-rule-variance-20261127U44VA"
PROBES = ("probe_sys_company_drafts", "probe_sys_october_drafts", "probe_sys_payroll_exports_all", "sys_rule_variance")


def restore_private(args):
    proof = json.loads((BASE / "backup.json").read_bytes())
    require(proof["source"] == "COMMUNITY_SYS_PREVIRED_COHORT_20261126U42L" and proof["sql_sha256"] ==
            "0c4e970e29579c6de38d71397a987682e97ff9a90027baad8c9e9b77f84bf606", "wrong-original-6.1-release")
    if not (ROOT / "restored.json").is_file():
        restore(args, proof)
    require(guards(DB) == guards(proof["source"]) and module_versions(DB)["step_payroll_oca_sys_history"] ==
            ["installed", "18.0.1.6.1"], "restored-history-or-guards-differ")
    assets = json.loads((BASE / "filestore-physical.json").read_bytes())
    require(assets["source"] == proof["source"] and assets["sql_sha256"] == proof["sql_sha256"] and
            digest(BASE / "filestore-extra.tar") == assets["extra_archive_sha256"], "wrong-original-extra-files")
    files = ROOT / "data/filestore" / DB
    restore_supplement(BASE / "filestore-extra.tar", assets["extras"], files)
    physical = inventory(files, object_catalog(attachments(DB, query)["references"]))
    require(len(physical) == 2698 and hashlib.sha256(json.dumps(physical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            == assets["tree_sha256"] == "71c9add47cf4265ee31555f42c02c8a819b8683154e53858490b22c6c11f8d1c",
            "restored-file-tree-differs")


def cases():
    baselines = []
    accepted = {"native": "b8f63c6e7d77bd343861fae1dfb724d2c16e7c3474ea273abaa2a58dcd466922",
                "community": "f8d6bbfaf1ca7723ec88c1e9f454da86f50132eb0cd7660af7271bf5da2f2cf0"}
    for name, sha in accepted.items():
        file = CODE / ("baseline-" + name + ".json")
        require(digest(file) == sha, "wrong-original-133-case-baseline")
        baselines.append(json.loads(file.read_bytes()))
    selections = [[r["source"] for r in data["samples"] if "draft" in r and not r["equals_stored"]] for data in baselines]
    require(selections[0] == selections[1] and len(selections[0]) == 33, "original-33-cases-required")
    return selections[0], baselines


def exercise(args, kind, selected):
    probes = ROOT / "probes"
    probes.mkdir(mode=0o755, exist_ok=True)
    probes.chmod(0o755)
    for name in PROBES:
        file = probes / (name + ".py")
        if not file.is_file():
            shutil.copyfile(CODE / file.name, file)
            file.chmod(0o644)
        require(digest(file) == digest(CODE / file.name), "probe-changed-since-restore")
    db = DB if kind == "community" else ORIGINAL
    script = f"""import sys,json
from pathlib import Path
sys.path.insert(0, {str(probes)!r})
from probe_sys_company_drafts import probe
from probe_sys_payroll_exports_all import snapshot
from odoo.modules.module import get_module_path,get_manifest
assert env.cr.dbname == {db!r}
if {kind!r} == 'community':
    app=env['ir.module.module'].search([('name','=','step_payroll_oca_sys_history'),('state','=','installed')])
    assert app.latest_version == get_manifest(app.name)['version'] == '18.0.1.6.1'
    assert Path(get_module_path(app.name)).samefile(Path({str(ROOT)!r})/'runtime/addons'/app.name)
before=snapshot(env)
result=probe(env,2,selected=set({selected!r}),summary=True,components=True)
assert before==snapshot(env)
result['preserved_tables']=sorted(before)
print('COMPONENTS='+json.dumps(result),flush=True)
"""
    output = ROOT / (kind + ".json")
    if output.is_file():
        return json.loads(output.read_bytes())
    log = ROOT / (kind + "-" + str(len(list(ROOT.glob(kind + "-*.log")))) + ".log")
    if kind == "community":
        status = odoo(args, "shell", [], log, script.encode())
    else:
        argv = ["unshare", "--net", "--", "runuser", "-u", "odoo", "--", "env", "PYTHONDONTWRITEBYTECODE=1",
                "/usr/bin/python3.10", "/opt/odoo18/odoo-bin", "shell", "-c", "/etc/odoo18-sys.conf",
                "-d", db, "--db-filter=^" + db + "$", "--db_host=/var/run/postgresql",
                "--data-dir=/opt/steps-validation/community-sys-recovery-20261126U40N/data", "--load=base,web",
                "--workers=0", "--max-cron-threads=0", "--no-http", "--stop-after-init", "--without-demo=all"]
        with log.open("xb") as handle:
            status = subprocess.run(argv, input=script.encode(), stdout=handle, stderr=handle).returncode
    rows = [json.loads(line.partition("=")[2]) for line in log.read_text().splitlines() if line.startswith("COMPONENTS=")]
    require(status == 0 and len(rows) == 1 and all(r.get("changes_by_rule") for r in rows[0]["samples"]), "component-probe-failed")
    save(output, rows[0])
    return rows[0]


def summarize(native, community, baselines):
    original = classify(native, community, *baselines)
    cases = {r["source"]: r["changes_by_rule"] for r in native["samples"]}
    require(cases == {r["source"]: r["changes_by_rule"] for r in community["samples"]}, "native-component-differences")
    first, changed = Counter(), Counter()
    flags = Counter()
    for rows in cases.values():
        first.update([tuple(sorted((r["sequence"], r["code"], r["rule"]) for r in rows if r["sequence"] == rows[0]["sequence"]))])
        for r in rows:
            changed[(r["sequence"], r["code"], r["rule"])] += 1
            flags[(r["code"], r["rule"], r["old_rows"], r["new_rows"], tuple(r["fields"]))] += 1
    return {"original_classification": original, "first_sequence_changes": [[[list(rule) for rule in k], n] for k, n in sorted(first.items())],
            "changed_components": [[*k, n] for k, n in sorted(changed.items())],
            "presence_and_value_fields": [[code, rule, old, new, list(fields), n] for (code, rule, old, new, fields), n in sorted(flags.items())]}


def main():
    os.umask(0o077)
    args = SimpleNamespace(database=DB, output=ROOT, sealed=BASE)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore_private(args)
        selected, baselines = cases()
        native, community = (exercise(args, kind, selected) for kind in ("native", "community"))
        result = summarize(native, community, baselines)
        initial = json.loads(gzip.decompress((BASE / "source-snapshot.json.gz").read_bytes()))
        delta = differences(initial, snapshot(DB))
        require(not any(v for k, v in delta.items() if k != "sequence_values"), "persisted-original-rows-or-schema-changed")
        result["private_sequence_advances"] = delta["sequence_values"]
        if not (ROOT / "classification.json").exists():
            save(ROOT / "classification.json", result)
        require(json.loads((ROOT / "classification.json").read_bytes()) == result, "previous-classification-differs")
        print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
