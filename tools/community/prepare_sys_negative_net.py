"""Clone the restored .6.2 release and update the SyS payroll provider in the isolated WSL instance."""
import argparse
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import prepare_sys_payslip_form_trial as trial
from seal_local_sys_193 import MEM, PORT, SOCKET, call, capture, inventory, psql


SOURCE = "COMMUNITY_SYS_PREVIRED_COHORT_20261127U48D"
SUFFIX = {"1": "F", "E": "E", "": "D"}[os.environ.get("SYS_NET_FINAL", "")]
DB = "COMMUNITY_SYS_PREVIRED_COHORT_20261127U49" + SUFFIX
WORK = Path("/dev/shm/sys-negative-net-u49" + SUFFIX.lower())
MODULE = "step_payroll_oca_sys_history"
RELEASE = "246f45bee249a4a674b076de75669561499dcd9d1d8492c77a4877f4abda6dde"


def clone():
    if not os.path.ismount("/dev/shm") or shutil.disk_usage("/dev/shm").free < 850 * 1024**2:
        raise ValueError("The restore requires reserved memory in the private WSL instance")
    if psql("SHOW data_directory", "postgres") != str(MEM / "postgres/cluster"):
        raise ValueError("Unexpected PostgreSQL cluster")
    query = f"SELECT latest_version FROM ir_module_module WHERE name='{MODULE}' AND state='installed'"
    if psql(query, SOURCE) != "18.0.1.6.2":
        raise ValueError("The source must be the recovered .6.2 release")
    WORK.mkdir(mode=0o711, exist_ok=True)
    if not psql(f"SELECT 1 FROM pg_database WHERE datname='{DB}'", "postgres"):
        call("postgres", ["createdb", "-h", SOCKET, "-p", PORT, "-O", "odoo", "-T", SOURCE, DB])
    if psql(query, DB) != "18.0.1.6.2":
        raise ValueError("The destination has already advanced beyond the original clone")
    for name, db in (("source", SOURCE), ("before", DB)):
        folder = WORK / name
        folder.mkdir(exist_ok=True)
        capture(db, SOCKET, PORT, folder)
    if (WORK / "source/snapshot.json.gz").read_bytes() != (WORK / "before/snapshot.json.gz").read_bytes():
        raise ValueError("The restored SQL data or catalogue differs")
    source = Path("/dev/shm/sys-u48-payslip-final/data/filestore") / SOURCE
    destination = WORK / "data/filestore" / DB
    if not destination.exists():
        shutil.copytree(source, destination)
        for directory, _, filenames in os.walk(WORK / "data"):
            os.chown(directory, 61018, 61018)
            for filename in filenames:
                os.chown(Path(directory) / filename, 61018, 61018)
    if inventory(source) != inventory(destination):
        raise ValueError("The restored physical files differ")
    shutil.copyfile(Path("/dev/shm/sys-u48-payslip-final/odoo.conf"), WORK / "odoo.conf")


def package():
    original = Path("/dev/shm/sys-u48-payslip-final/overlay") / MODULE
    repository = Path(__file__).resolve().parents[2] / MODULE
    contents = {}
    for source in sorted(original.rglob("*")):
        if source.is_file():
            name = source.relative_to(original)
            frozen = source.read_bytes()
            updated = (repository / name).read_bytes().replace(b"\r\n", b"\n")
            if name.as_posix() not in ("__init__.py", "__manifest__.py") and updated != frozen.replace(b"\r\n", b"\n"):
                raise ValueError("An unrelated .6.2 file changed: " + name.as_posix())
            contents[name] = updated.replace(b"\n", b"\r\n") if b"\r\n" in frozen else updated
    for name in (Path("negative_net.py"), Path("migrations/18.0.1.6.3/post-payroll-history.py")):
        contents[name] = (repository / name).read_bytes().replace(b"\r\n", b"\n")
    if len(contents) != 11:
        raise ValueError("The release needs eleven provider files")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in sorted(contents.items()):
            member = tarfile.TarInfo((Path(MODULE) / name).as_posix())
            member.size = len(data)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(data))
    payload = buffer.getvalue()
    checksum = hashlib.sha256(payload).hexdigest()
    archive = WORK / ("negative-net-" + checksum + ".tar")
    if archive.exists() and archive.read_bytes() != payload:
        raise ValueError("The existing package differs")
    archive.write_bytes(payload)
    return trial.extract_package(archive, checksum)


def upgrade(archive):
    checksum = trial.extract_package(archive, RELEASE) if archive else package()
    migration = WORK / "overlay" / MODULE / "migrations/18.0.1.6.3/post-payroll-history.py"
    script = f"""
import psycopg2
import runpy
migration = runpy.run_path({str(migration)!r})
with psycopg2.connect(dbname={DB!r}, user='postgres', host={SOCKET!r}, port={PORT}) as connection:
    with connection.cursor() as cursor:
        migration['migrate_guard'](cursor, owner=True)
"""
    call("postgres", ["python3.10", "-c", script])
    try:
        result = trial.odoo(["-u", MODULE], upgrade=True)
    except subprocess.CalledProcessError as exc:
        (WORK / "upgrade-error.log").write_bytes(exc.stderr)
        raise
    (WORK / "upgrade.log").write_bytes(result.stderr)
    print(checksum, result.stdout.decode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["clone", "upgrade"])
    parser.add_argument("--package", type=Path)
    args = parser.parse_args()
    trial.DB, trial.WORK = DB, WORK
    if args.stage == "clone":
        clone()
    else:
        upgrade(args.package)
