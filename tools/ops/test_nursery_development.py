"""Test an immutable nursery package on a neutralized, isolated Desarrollo copy."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess

from move_ecoplantas_to_development import (
    HERE, TARGET, config, dump, file_hash, get_user, odoo, package_hash, private_db,
    put_overlay, query, run, write_config,
)

MODULE = "step_nursery_operations"
ODOO = "/opt/odoo18/odoo-bin"


def check(run_id):
    assert os.geteuid() == 0
    assert re.fullmatch(r"[a-z0-9_]{1,16}", run_id)
    assert TARGET["database"] == "LAB_TAREAS" and TARGET["role"] == "qa"
    assert not query("LAB_TAREAS", "SELECT name FROM ir_module_module WHERE state IN ('to install','to remove','to upgrade')")
    repo = HERE.parents[1]
    stage = Path("/opt/steps-validation/nursery-dev_" + run_id)
    db = "ECOPLANTAS_DEV_QA_" + run_id
    assert not query("postgres", "SELECT 1 FROM pg_database WHERE datname=%s" % ("'" + db + "'"))
    os_user = get_user(TARGET["service"])
    user = pwd.getpwnam(os_user)
    stage.mkdir(mode=0o750)
    os.chown(stage, 0, user.pw_gid)
    source = repo / MODULE
    identity = package_hash(source)
    stage_addons = stage / "addons"
    shutil.copytree(source, stage_addons / MODULE, ignore=shutil.ignore_patterns("__pycache__"))
    assert package_hash(stage_addons / MODULE) == identity
    source_config = Path(TARGET["config"])
    source_hash = file_hash(source_config)
    cfg = config(source_config)
    data = stage / "data"
    data.mkdir(mode=0o700)
    os.chown(data, user.pw_uid, user.pw_gid)
    role = cfg["options"]["db_user"]
    cfg["options"].update({"db_name": db, "dbfilter": "^" + db + "$", "db_host": "127.0.0.1",
                           "data_dir": str(data), "workers": "0", "max_cron_threads": "0",
                           "list_db": "False", "proxy_mode": "False"})
    put_overlay(cfg, stage_addons)
    conf = stage / "copy.conf"
    write_config(cfg, conf)
    os.chown(conf, 0, user.pw_gid)
    conf.chmod(0o640)
    dump(TARGET["database"], stage / "development.dump")
    with private_db(db, role, stage):
        run("sudo", "-u", "postgres", "createdb", "-O", role, db)
        try:
            query(db, "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;")
            with (stage / "development.dump").open("rb") as stream:
                run("sudo", "-u", "postgres", "pg_restore", "--no-owner", "--no-acl", "--no-comments",
                    "--role", role, "-d", db, stdin=stream)
            query(db, "UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;")
            _neutralize(conf, db, os_user, stage)
            query(db, "UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;")
            uuid = "SELECT value FROM ir_config_parameter WHERE key='database.uuid'"
            assert query(db, uuid) != query(TARGET["database"], uuid)
            odoo(conf, db, os_user, ODOO, stage / "test.log",
                 args=("-i", MODULE, "--test-tags", "/" + MODULE, "--stop-after-init"))
            logfile = (stage / "test.log").read_text()
            result = re.search(r"0 failed, 0 error\(s\) of ([1-9][0-9]*)", logfile)
            assert result, str(stage / "test.log")
            assert not query(db, "SELECT id FROM ir_cron WHERE active UNION ALL SELECT id FROM ir_mail_server WHERE active")
        finally:
            run("sudo", "-u", "postgres", "dropdb", "--if-exists", db)
            (stage / "development.dump").unlink()
            conf.unlink()
    assert file_hash(source_config) == source_hash
    proof = {"package_sha256": identity, "test_count": int(result.group(1)), "database": "development copy"}
    (stage / "result.json").write_text(json.dumps(proof) + "\n")
    print("NURSERY_QA_OK " + json.dumps(proof), flush=True)


def _neutralize(conf, db, user, stage):
    log = stage / "neutralize.log"
    with log.open("w") as stream:
        subprocess.run(["sudo", "-u", user, "/usr/bin/python3.10", ODOO, "neutralize",
                        "-c", str(conf), "-d", db], stdout=stream, stderr=subprocess.STDOUT,
                       check=True, cwd="/tmp")
    odoo(conf, db, user, ODOO, stage / "copy_identity.log",
         "env['ir.config_parameter'].init(force=True)\nenv.cr.commit()\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    arguments = parser.parse_args()
    with open("/run/lock/steps-environments.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        check(arguments.run_id)
