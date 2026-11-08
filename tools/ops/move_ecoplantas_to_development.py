"""Move the EcoPlantas demo into its existing company in Desarrollo."""
import argparse
import ast
import configparser
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request

from manage_management import query, tree_hash
from manage_ecoplantas_greenhouse import TABLES, credentials, deliveries, preserve, snapshot
from provision_ecoplantas_demo import ROOT as SOURCE_ROOT, private_json, run

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REGISTRY = json.loads((HERE / "environments.json").read_text())
SOURCE = REGISTRY["environments"]["ecoplantas"]
TARGET = REGISTRY["environments"]["development"]
MODULES = ("step_costing_driver", "step_sawmill", "step_ecoplantas_greenhouse", "step_nursery_shared_costs")
NATIVE = ("maintenance", "mrp_maintenance")
CHECK = HERE / "ecoplantas_company_data.py"
BUSINESS = TABLES + ("res_company", "stock_warehouse", "stock_location", "stock_picking_type",
                     "mrp_bom_line", "mrp_routing_workcenter", "mrp_workorder", "mrp_workcenter",
                     "quality_point", "quality_check", "maintenance_equipment", "account_analytic_account",
                     "account_analytic_plan", "account_analytic_line", "step_sawmill_costing_driver")
PREVIEW_PORT = 41477


def config(path):
    result = configparser.ConfigParser(interpolation=None)
    assert result.read(path)
    return result


def dump(db, destination):
    with destination.open("xb") as stream:
        destination.chmod(0o600)
        run("sudo", "-u", "postgres", "pg_dump", "-Fc", db, stdout=stream)


def modules(db):
    return json.loads(query(db, "SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"))


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_hash(path):
    hash_value = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file() and "__pycache__" not in file.parts:
            hash_value.update(str(file.relative_to(path)).encode() + b"\0")
            hash_value.update(file.read_bytes())
    return hash_value.hexdigest()


def identity():
    assert not subprocess.check_output(["git", "status", "--porcelain", "--", *MODULES, "tools/ops"], cwd=REPO).strip()
    files = {name: package_hash(REPO / name) for name in MODULES}
    return {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
            "files": files, "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}


def get_user(service):
    name = subprocess.check_output(["systemctl", "show", "--value", "-p", "User", service], text=True).strip()
    assert name
    return name


def baseline():
    db = TARGET["database"]
    assert db == "LAB_TAREAS" and REGISTRY["policy"]["qa"] == "development"
    cfg = config(TARGET["config"])
    assert cfg["options"]["db_name"] == db
    access = json.loads((SOURCE_ROOT / "review-access-verified.json").read_text())
    source_uid = int(access["live"]["user_id"])
    login = query(SOURCE["database"], f"SELECT login FROM res_users WHERE id={source_uid}")
    literal = "'" + login.replace("'", "''") + "'"
    cid = int(query(db, "SELECT id FROM res_company WHERE lower(btrim(name))='ecoplantas' AND active AND parent_id IS NULL"))
    uid = int(query(db, "SELECT id FROM res_users WHERE active AND NOT share AND lower(login)=lower(" + literal + ")"))
    assert query(db, f"SELECT 1 FROM res_company_users_rel WHERE user_id={uid} AND cid={cid}") == "1"
    installed = modules(db)
    assert installed["step_sawmill"] == "18.0.1.0.1"
    assert not (set(MODULES) - {"step_sawmill"}) & installed.keys()
    assert not query(db, "SELECT name FROM ir_module_module WHERE state IN ('to install','to remove','to upgrade')")
    paths = [Path(path.strip()) for path in cfg["options"]["addons_path"].split(",")]
    effective = {}
    for module in ("step_sawmill", *NATIVE, "mrp", "stock", "quality_mrp", "account", "project"):
        origin = next(path / module for path in paths if (path / module / "__manifest__.py").is_file())
        effective[module] = [str(origin), tree_hash(origin)]
    # Refuse to replace any unpublished local Aserradero changes.
    old = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "68723562", "step_sawmill"], cwd=REPO, text=True).splitlines()
    sawmill = Path(effective["step_sawmill"][0])
    assert old
    for file in old:
        if Path(file).suffix in {".py", ".xml", ".csv", ".js", ".scss", ".css"}:
            tracked = subprocess.check_output(["git", "show", f"68723562:{file}"], cwd=REPO)
            assert (sawmill / Path(file).relative_to("step_sawmill")).read_bytes().replace(b"\r\n", b"\n") == tracked.replace(b"\r\n", b"\n"), file
    return {"cid": cid, "uid": uid, "source_uid": source_uid, "config": file_hash(Path(TARGET["config"])),
            "effective": effective, "installed": installed}


def odoo(config_path, db, user, binary, log, script=None, args=()):
    command = ["sudo", "-u", user, "/usr/bin/python3.10", str(binary)]
    if script is not None:
        command.append("shell")
    command += ["-c", str(config_path), "-d", db, "--db-filter=^" + db + "$",
                "--no-http", "--workers=0", "--max-cron-threads=0", "--without-demo=all", *args]
    result = subprocess.run(command, input=script, text=True, capture_output=True, cwd="/tmp")
    log.write_text(result.stdout + "\n" + result.stderr)
    log.chmod(0o600)
    assert result.returncode == 0, str(log)
    errors = [line for line in result.stderr.splitlines() if " ERROR " in line or " CRITICAL " in line]
    assert not [line for line in errors if "Some modules are not loaded" not in line or "['steps_api']" not in line], str(log)
    return result.stdout


def native(config_path, db, stage, state, payload, operation):
    code = CHECK.read_text(encoding="utf-8")
    code += f"\npayload=json.loads({json.dumps(payload, ensure_ascii=False)!r})\n"
    code += f"\nproof={operation}(env,payload,{state['cid']},{state['uid']})\n"
    code += "env.cr.commit()\n" if operation == "import_demo" else "env.cr.rollback()\n"
    code += "print('ECOPLANTAS_COMPANY_PROOF '+json.dumps(proof))\n"
    result = odoo(config_path, db, get_user(TARGET["service"]), "/opt/odoo18/odoo-bin", stage / (operation + ".log"), code)
    line, = [line for line in result.splitlines() if line.startswith("ECOPLANTAS_COMPANY_PROOF ")]
    return json.loads(line.split(" ", 1)[1])


def source_data(stage, state, label):
    code = CHECK.read_text(encoding="utf-8")
    code += f"\nresult=export_demo(env,{state['source_uid']})\nenv.cr.rollback()\n"
    code += "print('ECOPLANTAS_SOURCE_DATA '+json.dumps(result,default=str,ensure_ascii=False,sort_keys=True))\n"
    output = odoo(SOURCE["config"], SOURCE["database"], get_user(SOURCE["service"]),
                  SOURCE_ROOT / "runtime/odoo-bin", stage / (label + ".log"), code)
    line, = [line for line in output.splitlines() if line.startswith("ECOPLANTAS_SOURCE_DATA ")]
    return json.loads(line.split(" ", 1)[1])


def put_overlay(cfg, overlay):
    cfg["options"]["addons_path"] = str(overlay) + "," + cfg["options"]["addons_path"]


def write_config(cfg, target):
    with target.open("w") as stream:
        cfg.write(stream)


@contextmanager
def private_db(db, role, stage):
    assert re.fullmatch(r"ECOPLANTAS_DEV_QA_[a-z0-9_]{1,16}", db) and re.fullmatch(r"[a-zA-Z0-9_]+", role)
    hba = Path(query("postgres", "SHOW hba_file"))
    assert hba.name == "pg_hba.conf" and str(hba).startswith("/etc/postgresql/")
    original = hba.read_bytes()
    block = f'# STEPS ECOPLANTAS DEVELOPMENT COPY {db}\nhost "{db}" "{role}" 127.0.0.1/32 md5\n'.encode()
    assert block not in original
    (stage / "pg_hba_before.conf").write_bytes(original)
    (stage / "pg_hba_before.conf").chmod(0o600)
    try:
        hba.write_bytes(block + original)
        assert not query("postgres", "SELECT error FROM pg_hba_file_rules WHERE error IS NOT NULL")
        assert query("postgres", "SELECT pg_reload_conf()") == "t"
        yield
    finally:
        current = hba.read_bytes()
        assert current.count(block) == 1
        hba.write_bytes(current.replace(block, b"", 1))
        assert query("postgres", "SELECT pg_reload_conf()") == "t"


def store_copy(cfg, source_db, output):
    store = Path(cfg["options"]["data_dir"]) / "filestore" / source_db
    if store.exists():
        output.mkdir(parents=True)
        run("rsync", "-a", str(store) + "/", str(output) + "/")


def apply_stage(conf, db, logs, payload, state):
    before = snapshot(db, tables=BUSINESS)
    passwords, mail = credentials(db), deliveries(db)
    memberships = query(db, "SELECT cid,user_id FROM res_company_users_rel ORDER BY cid,user_id")
    settings = query(db, "SELECT key,md5(value) FROM ir_config_parameter WHERE key LIKE 'database.%' ORDER BY key")
    assert modules(db) == state["installed"]
    install = [module for module in (*NATIVE, *MODULES) if module not in state["installed"]]
    odoo(conf, db, get_user(TARGET["service"]), "/opt/odoo18/odoo-bin", logs / "modules.log",
         args=("-i", ",".join(install), "-u", "step_sawmill", "--stop-after-init"))
    versions = modules(db)
    for name in MODULES:
        expected = ast.literal_eval((REPO / name / "__manifest__.py").read_text())["version"]
        assert versions[name] == expected
    assert all(versions[name] == version for name, version in state["installed"].items() if name != "step_sawmill")
    assert set(NATIVE) <= versions.keys()
    result = native(conf, db, logs, state, payload, "import_demo")
    preserve(db, before, passwords, mail, tables=BUSINESS)
    assert query(db, "SELECT cid,user_id FROM res_company_users_rel ORDER BY cid,user_id") == memberships
    assert query(db, "SELECT key,md5(value) FROM ir_config_parameter WHERE key LIKE 'database.%' ORDER BY key") == settings
    return result, versions


def qa(stage, db):
    stage.mkdir(mode=0o750)
    os_user = get_user(TARGET["service"])
    unix = pwd.getpwnam(os_user)
    os.chown(stage, 0, unix.pw_gid)
    release = identity()
    state = baseline()
    payload = source_data(stage, state, "export")
    private_json(stage / "payload.json", payload)
    overlay = stage / "addons"
    for name in MODULES:
        shutil.copytree(REPO / name, overlay / name, ignore=shutil.ignore_patterns("__pycache__"))
        assert package_hash(overlay / name) == release["files"][name]
    dump(TARGET["database"], stage / "development.dump")
    cfg = config(TARGET["config"])
    data = stage / "data"
    data.mkdir(mode=0o750)
    store_copy(cfg, TARGET["database"], data / "filestore" / db)
    for path in (data, *data.rglob("*")):
        os.chown(path, unix.pw_uid, unix.pw_gid)
    role = cfg["options"]["db_user"]
    cfg["options"].update({"db_name": db, "dbfilter": "^" + db + "$", "db_host": "127.0.0.1",
                           "data_dir": str(data), "workers": "0", "max_cron_threads": "0",
                           "http_port": str(PREVIEW_PORT), "http_interface": "127.0.0.1", "proxy_mode": "False"})
    conf = stage / "copy.conf"
    write_config(cfg, conf)
    os.chown(conf, 0, unix.pw_gid)
    conf.chmod(0o640)
    assert not query("postgres", f"SELECT 1 FROM pg_database WHERE datname='{db}'")
    with private_db(db, role, stage):
        run("sudo", "-u", "postgres", "createdb", "-O", role, db)
        query(db, "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;")
        with (stage / "development.dump").open("rb") as stream:
            run("sudo", "-u", "postgres", "pg_restore", "--no-owner", "--no-acl", "--no-comments",
                "--role", role, "-d", db, stdin=stream)
        query(db, "UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;")
        odoo(conf, db, os_user, "/opt/odoo18/odoo-bin", stage / "neutralize.log",
             "env['ir.config_parameter'].init(force=True)\nenv.cr.commit()\n")
        uuid = "SELECT value FROM ir_config_parameter WHERE key='database.uuid'"
        assert query(db, uuid) != query(TARGET["database"], uuid)
        put_overlay(cfg, overlay)
        write_config(cfg, conf)
        imported, versions = apply_stage(conf, db, stage, payload, state)
        tested = native(conf, db, stage, state, payload, "exercise_demo")
        native(conf, db, stage, state, payload, "verify_demo")
    proof = {"release": release, "baseline": state, "source_sha256": file_hash(stage / "payload.json"),
             "versions": versions, "imported": imported, "exercise": tested}
    private_json(stage / "qa-passed.json", proof)
    print("ECOPLANTAS_DEVELOPMENT_QA_OK " + json.dumps({"release": release, "imported": imported, "exercise": tested}), flush=True)


def certified(stage):
    proof = json.loads((stage / "qa-passed.json").read_text())
    assert proof["release"] == identity()
    assert proof["source_sha256"] == file_hash(stage / "payload.json")
    assert proof["exercise"]["same_lot"] and proof["exercise"]["cost_confirmed_and_reversed"]
    assert proof["exercise"]["live_indicators"]
    for name, digest in proof["release"]["files"].items():
        assert package_hash(stage / "addons" / name) == digest
    return proof


def preview(stage, db):
    proof = certified(stage)
    conf = stage / "copy.conf"
    role = config(conf)["options"]["db_user"]
    unix = pwd.getpwnam(get_user(TARGET["service"]))
    command = ["/usr/bin/python3.10", "/opt/odoo18/odoo-bin", "-c", str(conf), "-d", db]
    with private_db(db, role, stage):
        state = proof["baseline"]
        request = {"login": "qa_ecoplantas_" + secrets.token_hex(8), "password": secrets.token_urlsafe(24),
                   "company": state["cid"], "db": db}
        script = f"""
from odoo import Command
assert env.cr.dbname.startswith('ECOPLANTAS_DEV_QA_')
review = env['res.users'].browse({state['uid']})
assert review.active and {state['cid']} in review.company_ids.ids
data = {request!r}
env['res.users'].with_context(no_reset_password=True, tracking_disable=True, mail_create_nosubscribe=True).create({{
    'name': 'Validación privada EcoPlantas', 'login': data['login'], 'password': data['password'],
    'company_id': review.company_id.id, 'company_ids': [Command.set(review.company_ids.ids)],
    'groups_id': [Command.set(review.groups_id.ids)], 'lang': review.lang, 'tz': review.tz,
}})
env.cr.commit()
print('ECOPLANTAS_BROWSER_COPY_ACCOUNT_READY')
"""
        odoo(conf, db, unix.pw_name, "/opt/odoo18/odoo-bin", stage / "preview-account.log", script)
        secret = stage / "browser-login.json"
        fd = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(request, stream)
        print("ECOPLANTAS_DEVELOPMENT_PREVIEW " + str(PREVIEW_PORT), flush=True)
        process = subprocess.Popen(command, cwd=stage, user=unix.pw_uid, group=unix.pw_gid,
                                   extra_groups=[], start_new_session=True)
        try:
            process.wait(timeout=240)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            pass
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            secret.unlink(missing_ok=True)


def deploy(stage):
    proof = certified(stage)
    state = baseline()
    assert proof["baseline"] == state, "Development changed since the private copy"
    browser = json.loads((stage / "browser-approved.json").read_text(encoding="utf-8-sig"))
    assert browser["sha256"] == proof["release"]["sha256"] and browser["visual_reviewed"]
    assert browser["company"] == state["cid"] and browser["other_company_unthemed"] and browser["cost_preview"]
    assert browser["workflow_navigation"] and browser["mobile_forms"]
    payload = json.loads((stage / "payload.json").read_text())
    assert source_data(stage, state, "source-recheck") == payload, "The source demo changed; certify a fresh export"
    release = Path("/opt/steps-managed/releases/development") / proof["release"]["commit"]
    assert not release.exists()
    shutil.copytree(stage / "addons", release, ignore=shutil.ignore_patterns("__pycache__"))
    for name, digest in proof["release"]["files"].items():
        assert package_hash(release / name) == digest
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path("/opt/steps_backups") / ("ecoplantas-company-" + stamp)
    backup.mkdir(mode=0o700)
    conf = Path(TARGET["config"])
    cfg = config(conf)
    dump(SOURCE["database"], backup / "standalone.dump")
    store_copy(config(SOURCE["config"]), SOURCE["database"], backup / "standalone-filestore")
    run("systemctl", "stop", TARGET["service"])
    try:
        shutil.copy2(conf, backup / "development.conf")
        (backup / "development.conf").chmod(0o600)
        dump(TARGET["database"], backup / "development.dump")
        store_copy(cfg, TARGET["database"], backup / "development-filestore")
        put_overlay(cfg, release)
        write_config(cfg, conf)
        result, versions = apply_stage(conf, TARGET["database"], backup, payload, state)
        assert versions == proof["versions"]
    except Exception:
        if "step_ecoplantas_greenhouse" not in modules(TARGET["database"]) and (backup / "development.conf").exists():
            conf.write_bytes((backup / "development.conf").read_bytes())
        raise
    finally:
        run("systemctl", "start", TARGET["service"])
    for attempt in range(12):
        try:
            with urllib.request.urlopen(TARGET["url"] + "/web/login?db=" + TARGET["database"], timeout=10) as response:
                assert response.status == 200 and b"password" in response.read()
            break
        except (urllib.error.URLError, TimeoutError):
            if attempt == 11:
                raise
            time.sleep(5)
    native(conf, TARGET["database"], backup, state, payload, "verify_demo")
    result.update(release=proof["release"], backup=str(backup), existing_records_preserved=True)
    private_json(stage / "deployed.json", result)
    print("ECOPLANTAS_DEVELOPMENT_DEPLOYED " + json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("qa", "preview", "deploy", "export"))
    parser.add_argument("run_id")
    args = parser.parse_args()
    assert os.geteuid() == 0 and re.fullmatch("[a-z0-9_]{1,16}", args.run_id)
    stage = Path("/opt/steps-validation/ecoplantas-company_" + args.run_id)
    db = "ECOPLANTAS_DEV_QA_" + args.run_id
    if args.action == "preview":
        def stop(_signum, _frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop)
    with open("/run/lock/steps-environments.lock", "a") as lease:
        print("ECOPLANTAS_DEVELOPMENT_WAITING_LEASE", flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        if args.action == "qa":
            qa(stage, db)
        elif args.action == "preview":
            preview(stage, db)
        elif args.action == "export":
            stage.mkdir(mode=0o700)
            payload = source_data(stage, baseline(), "export")
            private_json(stage / "payload.json", payload)
            print("ECOPLANTAS_EXPORT_OK " + str(len(payload["rows"])), flush=True)
        else:
            deploy(stage)


if __name__ == "__main__":
    main()
