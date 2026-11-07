"""Certify, preview and publish the isolated ECOPLANTAS layout."""
import argparse
import configparser
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request

from manage_ecoplantas_greenhouse import (
    ROOT, DB, USER, CONF, SERVICE, PRIVATE_BIN, baseline, backup, copy_access,
    credentials, deliveries, installed, odoo, preserve, private_json, query, run, sha,
    snapshot, tree_hash,
)

MODULE = "step_ecoplantas_greenhouse"
HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / MODULE
CHECK = HERE / "ecoplantas_layout_checks.py"
SCENARIO = HERE / "ecoplantas_greenhouse_scenario.py"
PREVIEW_PORT = 41476
SHARED_LOCK = "/run/lock/steps-environments.lock"


def read_config(path):
    cfg = configparser.ConfigParser(interpolation=None)
    assert cfg.read(path)
    return cfg


def extend_paths(cfg, overlay):
    root = str(ROOT / "addons")
    current = cfg["options"]["addons_path"].split(",")
    assert [value.strip() for value in current][0] == root
    assert not any("/layout-releases/" in item for item in current)
    cfg["options"]["addons_path"] = str(overlay) + "," + cfg["options"]["addons_path"]


@contextmanager
def fresh_copy(stage, db, overlay, *, path_setup=extend_paths):
    identity = pwd.getpwnam(USER)
    saved = stage / "source"
    backup(DB, saved)
    data = stage / "data"
    data.mkdir(mode=0o750)
    os.chown(data, identity.pw_uid, identity.pw_gid)
    cfg = read_config(CONF)
    path_setup(cfg, overlay)
    cfg["options"].update({
        "db_name": db, "dbfilter": "^" + db + "$", "data_dir": str(data),
        "max_cron_threads": "0", "workers": "0", "proxy_mode": "False",
        "http_interface": "127.0.0.1", "http_port": str(PREVIEW_PORT),
    })
    conf = stage / "copy.conf"
    with conf.open("x") as stream:
        cfg.write(stream)
    conf.chmod(0o640)
    os.chown(conf, 0, identity.pw_gid)
    assert not query("postgres", "SELECT 1 FROM pg_database WHERE datname='" + db + "'")
    with copy_access(db, stage):
        run("sudo", "-u", "postgres", "createdb", "-O", USER, db)
        query(db, "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;")
        with (saved / "database.dump").open("rb") as stream:
            run("sudo", "-u", "postgres", "pg_restore", "--no-owner", "--no-acl",
                "--no-comments", "--role", USER, "-d", db, stdin=stream)
        store = data / "filestore" / db
        if (saved / "filestore").exists():
            store.mkdir(parents=True)
            run("rsync", "-a", str(saved / "filestore") + "/", str(store) + "/")
            for path in data.rglob("*"):
                os.chown(path, identity.pw_uid, identity.pw_gid)
        query(db, "UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;")
        odoo(db, conf, stage, "neutralize", "env['ir.config_parameter'].init(force=True)\nenv.cr.commit()\n")
        uuid = "SELECT value FROM ir_config_parameter WHERE key='database.uuid'"
        assert query(db, uuid) != query(DB, uuid)
        yield conf


def native(db, conf, logs, user, *, configure=False, exercise=False):
    script = SCENARIO.read_text(encoding="utf-8") + "\n" + CHECK.read_text(encoding="utf-8")
    if configure:
        script += "\nenv['res.users'].browse(%d).write({'action_id': env.ref(%r).id})\n" % (user, MODULE + ".action_greenhouse")
    script += "\nresult=layout_check(env,%d,exercise=%r)\n" % (user, exercise)
    script += "env.cr.commit()\n" if configure else "env.cr.rollback()\n"
    script += "import json\nprint('ECOPLANTAS_LAYOUT_NATIVE '+json.dumps(result))\n"
    name = "layout-configure" if configure else "layout-exercise" if exercise else "layout-verify"
    text = odoo(db, conf, logs, name, script)
    line, = [line for line in text.splitlines() if line.startswith("ECOPLANTAS_LAYOUT_NATIVE ")]
    return json.loads(line.split(" ", 1)[1])


def install(db, conf, logs, user, expected):
    before, passwords, mail = snapshot(db), credentials(db), deliveries(db)
    active = query(db, "SELECT id FROM ir_cron WHERE active ORDER BY id")
    memberships = "SELECT gid,uid FROM res_groups_users_rel ORDER BY gid,uid"
    groups = query(db, memberships)
    assert MODULE not in expected and installed(db) == expected
    odoo(db, conf, logs, "layout-install", arguments=["-i", MODULE, "--stop-after-init"])
    versions = installed(db)
    assert versions.pop(MODULE) == "18.0.1.0.0" and versions == expected
    result = native(db, conf, logs, user, configure=True)
    preserve(db, before, passwords, mail)
    assert query(db, memberships) == groups
    assert query(db, "SELECT id FROM ir_cron WHERE active ORDER BY id") == active
    return result


def source_proof():
    repo = HERE.parents[1]
    assert not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all", "--", MODULE, "tools/ops"], cwd=repo).strip()
    return {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "sha256": tree_hash(SOURCE), "operation": sha(Path(__file__)), "checks": sha(CHECK),
    }


def qa(stage, db, user):
    source = source_proof()
    original = baseline()
    stage.mkdir(mode=0o750)
    os.chown(stage, 0, pwd.getpwnam(USER).pw_gid)
    overlay = stage / "addons"
    shutil.copytree(SOURCE, overlay / MODULE)
    assert tree_hash(overlay / MODULE) == source["sha256"]
    with fresh_copy(stage, db, overlay) as conf:
        result = install(db, conf, stage, user, original["installed"])
        exercise = native(db, conf, stage, user, exercise=True)
        native(db, conf, stage, user)
    private_json(stage / "qa-passed.json", {
        "source": source, "baseline": original, "user": user, "native": result, "exercise": exercise,
    })
    print("ECOPLANTAS_LAYOUT_QA_OK " + json.dumps({"source": source, "exercise": exercise}), flush=True)


def proof_for(stage, user):
    proof = json.loads((stage / "qa-passed.json").read_text())
    assert proof["user"] == user and proof["source"] == source_proof()
    assert tree_hash(stage / "addons" / MODULE) == proof["source"]["sha256"]
    assert proof["exercise"]["same_manufactured_lot"] and proof["exercise"]["remaining_units"] == 40
    return proof


def preview(stage, db, user):
    proof_for(stage, user)
    serve_preview(stage, db)


def serve_preview(stage, db):
    conf = stage / "copy.conf"
    identity = pwd.getpwnam(USER)
    cmd = ["/usr/bin/python3.10", str(PRIVATE_BIN), "-c", str(conf), "-d", db]
    print("ECOPLANTAS_LAYOUT_PREVIEW " + str(PREVIEW_PORT), flush=True)
    with copy_access(db, stage):
        server = subprocess.Popen(cmd, cwd=stage, user=identity.pw_uid, group=identity.pw_gid,
                                  extra_groups=[], start_new_session=True)
        try:
            server.wait(timeout=180)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            pass
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


def wait_for_https():
    for attempt in range(12):
        try:
            with urllib.request.urlopen("https://ecoplantas.stepsapp.cl/web/login?db=ECOPLANTAS", timeout=10) as response:
                assert response.status == 200 and b"password" in response.read()
            return
        except (urllib.error.URLError, TimeoutError):
            if attempt == 11:
                raise
            time.sleep(5)


def deploy(stage, user):
    proof = proof_for(stage, user)
    browser = json.loads((stage / "browser-approved.json").read_text(encoding="utf-8-sig"))
    assert browser["sha256"] == proof["source"]["sha256"] and browser["visual_reviewed"] is True
    assert browser["desktop"] and browser["mobile"] and browser["home"] and len(browser["destinations"]) == 7
    assert proof["baseline"] == baseline(), "ECOPLANTAS changed since the fresh copy"
    release = ROOT / "layout-releases" / proof["source"]["commit"]
    assert not release.exists()
    shutil.copytree(stage / "addons", release, ignore=shutil.ignore_patterns("__pycache__"))
    assert tree_hash(release / MODULE) == proof["source"]["sha256"]
    saved = ROOT / ("layout-backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    cfg = read_config(CONF)
    extend_paths(cfg, release)
    run("systemctl", "stop", SERVICE)
    try:
        backup(DB, saved)
        with CONF.open("w") as stream:
            cfg.write(stream)
        result = install(DB, CONF, saved, user, proof["baseline"]["installed"])
    except Exception:
        if (saved / "odoo.conf").is_file() and MODULE not in installed(DB):
            CONF.write_bytes((saved / "odoo.conf").read_bytes())
        raise
    finally:
        run("systemctl", "start", SERVICE)
    wait_for_https()
    native(DB, CONF, saved, user)
    result.update(backup=str(saved), source=proof["source"], credentials_preserved=True)
    private_json(stage / "deployed.json", result)
    print("ECOPLANTAS_LAYOUT_DEPLOYED " + json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("qa", "preview", "deploy"))
    parser.add_argument("run_id")
    args = parser.parse_args()
    assert os.geteuid() == 0 and re.fullmatch("[a-z0-9_]{1,16}", args.run_id)
    access = json.loads((ROOT / "review-access-verified.json").read_text())
    assert access["https_authenticated"] and access["live"]["internal_user"]
    user = access["live"]["user_id"]
    stage = Path("/opt/steps-validation/ecoplantas-layout_" + args.run_id)
    db = "ECOPLANTAS_GH_QA_" + args.run_id
    if args.action == "preview":
        def stop(_signum, _frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop)
    with open(SHARED_LOCK, "a") as lock:
        print("ECOPLANTAS_LAYOUT_WAITING_LEASE", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == "qa":
            qa(stage, db, user)
        elif args.action == "preview":
            preview(stage, db, user)
        else:
            deploy(stage, user)


if __name__ == "__main__":
    main()
