"""Restore the independent SyS payslip-form trial in the existing WSL memory-only PostgreSQL instance."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

from load_steps_sales_extension import guarded_command
from seal_local_sys_193 import DB as BASE, MEM, PORT, SOCKET, call, capture, inventory, psql, sha


FINAL = os.environ.get("SYS_PAYSLIP_FORM_FINAL") == "1"
DB = "COMMUNITY_SYS_PREVIRED_COHORT_20261127U48" + ("D" if FINAL else "C")
WORK = Path("/dev/shm/sys-u48-payslip-final" if FINAL else "/dev/shm/sys-u48-payslip")
SEALED = MEM / "from-durable-kit"
MODULE = "step_payroll_oca_sys_history"
FINAL_PACKAGE = "e1f3d645ce6ca3b1c967114c72efb6db8c33c8e70c391d258caf6eb58ec27642"


def restore():
    if (not os.path.ismount("/dev/shm") or shutil.disk_usage("/dev/shm").free < 850 * 1024**2
            or psql("SHOW data_directory", "postgres") != str(MEM / "postgres/cluster")
            or sha(SEALED / "release.json") != "35dfde4c6734efcb9575d7957381d06d1874326d245605b11d7d84e4f08942da"):
        raise ValueError("Verified local product and reserved memory capacity required")
    WORK.mkdir(mode=0o711, exist_ok=True)
    release = json.loads((SEALED / "release.json").read_bytes())
    dump = SEALED / "source.dump"
    if sha(dump) != release["files"][dump.name]:
        raise ValueError("Product SQL differs")
    if not psql("SELECT 1 FROM pg_database WHERE datname='" + DB + "'", "postgres"):
        call("postgres", ["createdb", "-h", SOCKET, "-p", PORT, "-O", "odoo", "-T", "template0", "-E", "UTF8",
                          "--lc-collate=C", "--lc-ctype=C.UTF-8", DB])
    if not psql("SELECT to_regclass('public.hr_payslip')", DB):
        if psql("SELECT count(*) FROM pg_tables WHERE schemaname='public'", DB) != "0":
            raise ValueError("Expected empty isolated target")
        with dump.open("rb") as source:
            call("postgres", ["pg_restore", "-h", SOCKET, "-p", PORT, "-d", DB, "--no-tablespaces",
                              "--single-transaction", "--exit-on-error"], stdin=source)
    before = WORK / "before"
    before.mkdir(exist_ok=True)
    if capture(DB, SOCKET, PORT, before) != json.loads(gzip.decompress((SEALED / "snapshot.json.gz").read_bytes())):
        raise ValueError("Restored rows, counters or catalogue differ")
    store = WORK / "data/filestore" / DB
    if not store.exists():
        shutil.copytree(MEM / "data/filestore" / BASE, store)
        for directory, _, files in os.walk(WORK / "data"):
            os.chown(directory, 61018, 61018)
            for name in files:
                os.chown(Path(directory) / name, 61018, 61018)
    if inventory(store) != json.loads(gzip.decompress((SEALED / "filestore.json.gz").read_bytes())):
        raise ValueError("Physical files differ")
    (WORK / "odoo.conf").write_text("[options]\ndb_user = odoo\nlist_db = False\nlog_level = warn\n"
                                    "db_host = " + SOCKET + "\ndb_port = " + str(PORT) + "\n")


def package():
    repo = Path(__file__).resolve().parents[2]
    original = Path("/var/tmp/steps-community-qa-focal/work/sys-fg-code/addons") / MODULE
    sources = [path.relative_to(repo) for path in sorted((repo / MODULE).rglob("*"))
               if path.is_file() and "__pycache__" not in path.parts]
    if len(sources) != 9:
        raise ValueError("Expected nine files in the SyS form provider")
    original_names = {p.relative_to(original.parent) for p in original.rglob("*") if p.is_file()}
    if set(sources) - original_names != {Path(MODULE) / "payslip_form.py"} or original_names - set(sources):
        raise ValueError("Unexpected module files")
    with io.BytesIO() as buffer:
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for name in sources:
                data = (repo / name).read_bytes().replace(b"\r\n", b"\n")
                if name.name != "payslip_form.py":
                    frozen = (original.parent / name).read_bytes()
                    if name.name not in {"__init__.py", "__manifest__.py"} and data != frozen.replace(b"\r\n", b"\n"):
                        raise ValueError("An unrelated original module file changed")
                    if b"\r\n" in frozen:
                        data = data.replace(b"\n", b"\r\n")
                item = tarfile.TarInfo(name.as_posix())
                item.mode, item.size = 0o644, len(data)
                archive.addfile(item, io.BytesIO(data))
        payload = buffer.getvalue()
    checksum = hashlib.sha256(payload).hexdigest()
    output = WORK / ("operator-form-" + checksum + ".tar")
    if output.exists() and output.read_bytes() != payload:
        raise ValueError("The existing accepted candidate package differs")
    output.write_bytes(payload)
    return extract_package(output, checksum)


def extract_package(output, expected=FINAL_PACKAGE):
    if sha(output) != expected:
        raise ValueError("The operator payslip package differs from its accepted release")
    with tarfile.open(output) as archive:
        for item in archive:
            name = Path(item.name)
            if not item.isfile() or name.parts[0] != MODULE or name.is_absolute() or ".." in name.parts:
                raise ValueError("Unexpected operator package member")
            path = WORK / "overlay" / item.name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.extractfile(item).read())
    return expected


def odoo(args, source=None, upgrade=False):
    roots = [WORK / "overlay", MEM / "overlay", "/work/sys-fg-code/addons", "/work/sys-fg-code/odoo/addons"]
    cmd = ["python3.10", "/work/sys-fg-code/odoo-bin", *args, "-c", str(WORK / "odoo.conf"), "-d", DB,
           "--db-filter=^" + DB + "$", "--addons-path=" + ",".join(map(str, roots)),
           "--data-dir=" + str(WORK / "data"), "--no-http", "--max-cron-threads=0", "--workers=0",
           "--stop-after-init", "--load=base,web"]
    if upgrade:
        if args != ["-u", MODULE]:
            raise ValueError("Only this private payslip module may be updated")
        code = WORK / "code"
        code.mkdir(exist_ok=True)
        for name in ("load_steps_sales_extension.py", "preflight_original_history_storage.py"):
            shutil.copyfile(Path(__file__).with_name(name), code / name)
        frozen = json.loads(gzip.decompress((WORK / "before/snapshot.json.gz").read_bytes()))["snapshot"]
        cmd = guarded_command(cmd, WORK, frozen)
    relay = Path(__file__).with_name("run_focal_print_command.py")
    return subprocess.run([sys.executable, str(relay), "--user", "odoo", "--sys-payslip-form", "--", *cmd],
                          input=source, capture_output=True, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--restore", action="store_true")
    group.add_argument("--upgrade", action="store_true")
    parser.add_argument("--package", type=Path, help="Use the verified release TAR directly for the upgrade")
    args = parser.parse_args()
    if args.restore:
        restore()
    else:
        checksum = extract_package(args.package) if args.package is not None else package()
        try:
            result = odoo(["-u", MODULE], upgrade=True)
        except subprocess.CalledProcessError as exc:
            (WORK / "upgrade-error.log").write_bytes(exc.stderr)
            raise
        (WORK / "upgrade.log").write_bytes(result.stderr)
        print(checksum, result.stdout.decode().strip())
