"""Stage and promote T50 against existing Odoo modules, preserving other tickets."""
import argparse
import configparser
import datetime
import hashlib
import json
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tarfile

MODULE = "step_management_costs_agriculture"
ENVIRONMENTS = {
    "development": ("odoo18-dev", "/etc/dev_odoo18.conf", "LAB_TAREAS", "odoo", "/opt/dev_odoo18/odoo_agriculture"),
    "cerro": ("odoo18-cerroelplomo", "/etc/odoo18-cerroelplomo.conf", "CERRO_EL_PLOMO", "cerro_odoo18", "/opt/cerroelplomo_odoo18/steps_addons"),
}
# Confirmed before T50 and reproduced in the baseline clone. This missing
# unrelated addon does not prevent registry startup or the estimation tests.
KNOWN_BASELINE_ERROR = "Some modules are not loaded, some dependencies or manifest may be missing: ['steps_api']"


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def unexpected_errors(text):
    return [line for line in text.splitlines() if " ERROR " in line and not line.endswith(KNOWN_BASELINE_ERROR + " ") and not line.endswith(KNOWN_BASELINE_ERROR)]


def overlay(release, root):
    files = []
    with tarfile.open(release) as archive:
        for member in archive.getmembers():
            target = (root / member.name).resolve()
            assert target.is_relative_to(root.resolve()) and not member.issym() and not member.islnk()
            if member.isfile():
                assert member.name.startswith(MODULE + "/"), member.name
                files.append(member.name)
        archive.extractall(root)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["qa", "deploy", "verify"])
    parser.add_argument("environment", choices=ENVIRONMENTS)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    service, conf, database, user, addons = ENVIRONMENTS[args.environment]
    config = configparser.ConfigParser(interpolation=None)
    config.read(conf)
    options = config["options"]
    assert re.fullmatch(r"[A-Za-z0-9_]{1,24}", args.run_id)
    stage = Path("/opt/steps-validation") / ("t50_" + args.environment + "_" + args.run_id)
    qa_db = "T50_QA_" + args.environment.upper() + "_" + args.run_id
    python = "/usr/bin/python3.10"
    base_command = ["sudo", "-u", user, python, "/opt/odoo18/odoo-bin", "-c", conf, "--no-http", "--max-cron-threads=0"]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.action == "qa":
        if not stage.exists():
            stage.mkdir(parents=True, mode=0o750)
            shutil.chown(stage, user=user)
            shutil.copytree(Path(addons) / MODULE, stage / MODULE, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            files = overlay(args.release, stage)
            baseline = {relative: digest(Path(addons) / relative) for relative in files}
            (stage / "baseline.json").write_text(json.dumps(baseline, indent=2))
            with (stage / "source.dump").open("wb") as stream:
                run(["sudo", "-u", "postgres", "pg_dump", "-Fc", database], stdout=stream)
            run(["sudo", "-u", "postgres", "createdb", "-O", options["db_user"], qa_db])
            with (stage / "source.dump").open("rb") as stream:
                run(["sudo", "-u", "postgres", "pg_restore", "--no-owner", "--role", options["db_user"], "-d", qa_db], stdin=stream)
        else:
            overlay(args.release, stage)
        log = stage / ("qa-" + stamp + ".log")
        print("T50_QA_BEGIN", qa_db, str(log), flush=True)
        command = base_command + ["-d", qa_db, "--addons-path", str(stage) + "," + options["addons_path"],
                                  "--http-interface=127.0.0.1", "--http-port=0", "--gevent-port=0",
                                  "-u", MODULE, "--stop-after-init", "--test-enable", "--test-tags",
                                  "/step_management_costs_agriculture:TestEstimationCatalog,/step_management_costs_agriculture:TestAgricultureBridge", "--logfile", str(log)]
        result = subprocess.run(command)
        text = log.read_text(errors="replace")
        lines = [line for line in text.splitlines() if any(word in line for word in ["Starting Test", "failed", "ERROR", "FAIL", "T50 linked", "tests.stats", "tests.result"])]
        print("\n".join(lines[-90:]), flush=True)
        assert result.returncode == 0 and "0 failed, 0 error(s)" in text and "TestEstimationCatalog" in text and not unexpected_errors(text), f"QA failed: {log}"
        (stage / "qa_passed.json").write_text(json.dumps({"commit": args.commit, "release_sha256": digest(args.release), "database": qa_db, "log": str(log)}))
        print("T50_QA_OK", qa_db, flush=True)
        return
    passed = json.loads((stage / "qa_passed.json").read_text())
    assert passed["commit"] == args.commit and passed["release_sha256"] == digest(args.release)
    if args.action == "deploy":
        baseline = json.loads((stage / "baseline.json").read_text())
        for relative, original in baseline.items():
            assert digest(Path(addons) / relative) == original, "Concurrent change: " + relative
        backup = Path("/opt/steps_backups") / ("t50_" + args.environment + "_" + stamp)
        backup.mkdir(parents=True, mode=0o700)
        print("T50_BACKUP", str(backup), flush=True)
        run(["systemctl", "stop", service])
        try:
            with (backup / (database + ".dump")).open("wb") as stream:
                run(["sudo", "-u", "postgres", "pg_dump", "-Fc", database], stdout=stream)
            shutil.copytree(Path(addons) / MODULE, backup / MODULE)
            files = overlay(args.release, Path(addons))
            account = pwd.getpwnam(user)
            for relative in files:
                path = Path(addons) / relative
                shutil.chown(path, user=account.pw_uid, group=account.pw_gid)
                assert digest(path) == digest(stage / relative), relative
            log = stage / ("deploy-" + stamp + ".log")
            command = base_command + ["-d", database, "-u", MODULE, "--stop-after-init", "--logfile", str(log)]
            result = subprocess.run(command)
            text = log.read_text(errors="replace")
            print("\n".join(line for line in text.splitlines() if "T50 linked" in line or "ERROR" in line), flush=True)
            assert result.returncode == 0 and "Modules loaded." in text and not unexpected_errors(text), f"Upgrade failed: {log}"
            (backup / "deployment.json").write_text(json.dumps({"commit": args.commit, "database": database, "log": str(log), "files": {name: digest(Path(addons) / name) for name in files}}, indent=2))
        finally:
            run(["systemctl", "start", service])
        run(["systemctl", "is-active", "--quiet", service])
    command = base_command[:5] + ["shell"] + base_command[5:] + ["-d", database, "--logfile=/dev/null"]
    probe = Path(__file__).with_name("verify_odoo.py").read_text()
    result = subprocess.run(command, input=probe, text=True, capture_output=True)
    (stage / ("verify-" + stamp + ".log")).write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and "T50_VERIFY_OK" in result.stdout, result.stdout + result.stderr
    print(result.stdout.strip(), flush=True)
    print("T50_DEPLOY_OK", args.environment, args.commit, flush=True)


if __name__ == "__main__":
    main()
