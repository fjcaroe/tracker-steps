"""Certify and publish weekly shared costs only in the ECOPLANTAS demo."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import subprocess

from manage_ecoplantas_greenhouse import (
    ROOT, DB, USER, CONF, SERVICE, TABLES, backup, baseline, credentials,
    deliveries, installed, odoo, preserve, private_json, query, run, snapshot, tree_hash,
)
from manage_ecoplantas_layout import SHARED_LOCK, fresh_copy, read_config, serve_preview, wait_for_https

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FEATURE = "step_nursery_shared_costs"
DRIVER = "step_costing_driver"
MODULES = (DRIVER, FEATURE, "step_sawmill")
VERSIONS = {FEATURE: "18.0.1.0.0", DRIVER: "18.0.1.0.0"}
CHECK = HERE / "ecoplantas_cost_checks.py"
LEGACY = "68723562c5c543667d50be9af42168b61458b8b6"
BUSINESS = TABLES + ("account_analytic_plan", "account_analytic_account", "account_analytic_line")


def release_identity():
    assert not subprocess.check_output(["git", "status", "--porcelain", "--", *MODULES, "tools/ops"], cwd=REPO).strip()
    files = {module: tree_hash(REPO / module) for module in MODULES}
    return {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "files": files, "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
    }


def source_state():
    result = baseline()
    previous = json.loads(Path("/opt/steps-validation/ecoplantas-layout_layout5/deployed.json").read_text())
    live_layout = ROOT / "layout-releases" / previous["source"]["commit"] / "step_ecoplantas_greenhouse"
    assert tree_hash(live_layout) == previous["source"]["sha256"]
    assert result["installed"]["step_ecoplantas_greenhouse"] == "18.0.1.0.0"
    assert not (VERSIONS.keys() & result["installed"].keys())
    result["layout"] = previous["source"]["sha256"]
    return result


def prepend(cfg, overlay):
    paths = [path.strip() for path in cfg["options"]["addons_path"].split(",")]
    assert paths[-1] == str(ROOT / "addons")
    assert all(Path(path).resolve().is_relative_to(ROOT / "layout-releases") for path in paths[:-1])
    cfg["options"]["addons_path"] = ",".join([str(overlay), *paths])


def stage_release(stage):
    stage.mkdir(mode=0o750)
    os.chown(stage, 0, pwd.getpwnam(USER).pw_gid)
    identity = release_identity()
    overlay = stage / "addons"
    for module in MODULES:
        shutil.copytree(REPO / module, overlay / module, ignore=shutil.ignore_patterns("__pycache__"))
        assert tree_hash(overlay / module) == identity["files"][module]
    return identity, overlay


def native(db, conf, stage, uid, *, prepare=False, exercise=False):
    code = CHECK.read_text(encoding="utf-8")
    if prepare:
        code += f"\nreview = env['res.users'].browse({uid})\n"
        code += "assert review.has_group('account.group_account_manager')\n"
        code += "review.write({'groups_id': [Command.link(env.ref('analytic.group_analytic_accounting').id)]})\n"
    code += f"\nproof = verify_costs(env, {uid}, prepare={prepare!r}, exercise={exercise!r})\n"
    code += "env.cr.commit()\n" if prepare else "env.cr.rollback()\n"
    code += "import json\nprint('ECOPLANTAS_COST_NATIVE ' + json.dumps(proof))\n"
    label = "cost-prepare" if prepare else "cost-exercise" if exercise else "cost-verify"
    output = odoo(db, conf, stage, label, code)
    line, = [line for line in output.splitlines() if line.startswith("ECOPLANTAS_COST_NATIVE ")]
    return json.loads(line.split(" ", 1)[1])


def install(db, conf, stage, uid, expected):
    before, passwords, mail = snapshot(db, tables=BUSINESS), credentials(db), deliveries(db)
    active = query(db, "SELECT id FROM ir_cron WHERE active ORDER BY id")
    memberships = "SELECT gid,uid FROM res_groups_users_rel ORDER BY gid,uid"
    groups = set(query(db, memberships).splitlines())
    analytic_group = query(db, "SELECT res_id FROM ir_model_data WHERE module='analytic' AND name='group_analytic_accounting'")
    assert analytic_group.isdecimal()
    assert installed(db) == expected
    odoo(db, conf, stage, "cost-install", arguments=["-i", FEATURE, "--stop-after-init"])
    assert installed(db) == dict(expected, **VERSIONS)
    result = native(db, conf, stage, uid, prepare=True)
    preserve(db, before, passwords, mail, tables=BUSINESS)
    assert set(query(db, memberships).splitlines()) == groups | {f"{analytic_group}|{uid}"}
    assert query(db, "SELECT id FROM ir_cron WHERE active ORDER BY id") == active
    return result


def qa(stage, db, uid):
    identity, overlay = stage_release(stage)
    original = source_state()
    with fresh_copy(stage, db, overlay, path_setup=prepend) as conf:
        result = install(db, conf, stage, uid, original["installed"])
        exercise = native(db, conf, stage, uid, exercise=True)
        native(db, conf, stage, uid)
    private_json(stage / "qa-passed.json", {
        "release": identity, "baseline": original, "uid": uid, "preview": result, "exercise": exercise,
    })
    print("ECOPLANTAS_COST_QA_OK " + json.dumps({"release": identity, "exercise": exercise}), flush=True)


def legacy(stage, db):
    identity, overlay = stage_release(stage)
    legacy_overlay = stage / "legacy"
    legacy_overlay.mkdir()
    archive = subprocess.check_output(["git", "archive", LEGACY, "step_sawmill"], cwd=REPO)
    run("tar", "-xf", "-", "-C", str(legacy_overlay), input=archive)
    with fresh_copy(stage, db, legacy_overlay, path_setup=prepend) as conf:
        odoo(db, conf, stage, "sawmill-original", arguments=["-i", "step_sawmill", "--stop-after-init"])
        original = odoo(db, conf, stage, "sawmill-seed", """
driver = env['step.sawmill.costing.driver'].create({'name': 'Driver existente QA', 'sequence': 17})
model = env.ref('step_sawmill.model_step_sawmill_costing_driver')
env.cr.commit()
print('DRIVER_IDS', driver.id, model.id)
""")
        ids, = [line.split()[1:] for line in original.splitlines() if line.startswith("DRIVER_IDS ")]
        driver_id, model_id = map(int, ids)
        cfg = read_config(conf)
        prefix, remaining = cfg["options"]["addons_path"].split(",", 1)
        assert prefix == str(legacy_overlay)
        cfg["options"]["addons_path"] = str(overlay) + "," + remaining
        with conf.open("w") as stream:
            cfg.write(stream)
        odoo(db, conf, stage, "sawmill-upgrade", arguments=[
            "-i", DRIVER, "-u", "step_sawmill", "--stop-after-init",
        ])
        after = odoo(db, conf, stage, "sawmill-verify", f"""
driver = env['step.sawmill.costing.driver'].browse({driver_id})
assert driver.exists() and driver.name == 'Driver existente QA' and driver.sequence == 17
assert env.ref('step_costing_driver.model_step_sawmill_costing_driver').id == {model_id}
assert env.ref('step_sawmill.model_step_sawmill_costing_driver').id == {model_id}
assert env.ref('step_sawmill.access_step_sawmill_costing_driver_manager').model_id.id == {model_id}
assert env.ref('step_sawmill.action_step_sawmill_costing_driver').res_model == driver._name
env.cr.rollback()
print('SAWMILL_DRIVER_PRESERVED')
""")
        assert "SAWMILL_DRIVER_PRESERVED" in after
    private_json(stage / "legacy-passed.json", {"release": identity, "same_model": True, "same_record": True})
    print("ECOPLANTAS_COST_LEGACY_OK", flush=True)


def certified(stage, uid):
    proof = json.loads((stage / "qa-passed.json").read_text())
    assert proof["uid"] == uid and proof["release"] == release_identity()
    for module, digest in proof["release"]["files"].items():
        assert tree_hash(stage / "addons" / module) == digest
    assert proof["exercise"]["posted_source_preserved"] and proof["exercise"]["reversed"]
    return proof


def deploy(stage, uid, legacy_stage):
    proof = certified(stage, uid)
    old = json.loads((legacy_stage / "legacy-passed.json").read_text())
    assert old["same_model"] and old["same_record"]
    assert all(old["release"]["files"][module] == proof["release"]["files"][module]
               for module in (DRIVER, "step_sawmill"))
    browser = json.loads((stage / "browser-approved.json").read_text(encoding="utf-8-sig"))
    assert browser["sha256"] == proof["release"]["sha256"] and browser["visual_reviewed"] and browser["workflow"]
    assert proof["baseline"] == source_state()
    overlay = ROOT / "cost-releases" / proof["release"]["commit"]
    assert not overlay.exists()
    for module in VERSIONS:
        shutil.copytree(stage / "addons" / module, overlay / module, ignore=shutil.ignore_patterns("__pycache__"))
        assert tree_hash(overlay / module) == proof["release"]["files"][module]
    saved = ROOT / ("cost-backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    cfg = read_config(CONF)
    prepend(cfg, overlay)
    run("systemctl", "stop", SERVICE)
    try:
        backup(DB, saved)
        with CONF.open("w") as stream:
            cfg.write(stream)
        result = install(DB, CONF, saved, uid, proof["baseline"]["installed"])
    except Exception:
        if (saved / "odoo.conf").is_file() and FEATURE not in installed(DB):
            CONF.write_bytes((saved / "odoo.conf").read_bytes())
        raise
    finally:
        run("systemctl", "start", SERVICE)
    wait_for_https()
    native(DB, CONF, saved, uid)
    result.update(release=proof["release"], backup=str(saved), preserved=True)
    private_json(stage / "deployed.json", result)
    print("ECOPLANTAS_COST_DEPLOYED " + json.dumps(result), flush=True)


def stage_path(run_id):
    assert re.fullmatch("[a-z0-9_]{1,16}", run_id)
    return Path("/opt/steps-validation/ecoplantas-cost_" + run_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("qa", "legacy", "preview", "deploy"))
    parser.add_argument("run_id")
    parser.add_argument("--legacy-run")
    args = parser.parse_args()
    assert os.geteuid() == 0
    stage = stage_path(args.run_id)
    db = "ECOPLANTAS_GH_QA_" + args.run_id
    access = json.loads((ROOT / "review-access-verified.json").read_text())
    uid = access["live"]["user_id"]
    assert access["https_authenticated"] and access["live"]["internal_user"]
    if args.action == "preview":
        def stop(_signum, _frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop)
    with open(SHARED_LOCK, "a") as lease:
        print("ECOPLANTAS_COST_WAITING_LEASE", flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        if args.action == "qa":
            qa(stage, db, uid)
        elif args.action == "legacy":
            legacy(stage, db)
        elif args.action == "preview":
            certified(stage, uid)
            serve_preview(stage, db)
        else:
            deploy(stage, uid, stage_path(args.legacy_run))


if __name__ == "__main__":
    main()
