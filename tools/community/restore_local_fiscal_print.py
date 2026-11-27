"""Restore the frozen combined SyS release on the workstation and verify its physical manifests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

from run_focal_print_command import ROOT

DB = "COMMUNITY_SYS_FISCAL_PRINT_20261127U45P"
INDEX = "b033989da829ee87fa7233e3883f68cd1130eb52a4eb37ec8ebb8185e4d6c7e6"
WORK = ROOT / "work/sys-print"
RUNTIME = ROOT / "work/sys-fg-code"
STORE = WORK / "data/filestore" / DB


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_object(archive, member, root, mode, user):
    rel = Path(member.name)
    if rel.is_absolute() or ".." in rel.parts or not member.isfile():
        raise ValueError("Unexpected archive member")
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != path:
        raise ValueError("Unexpected symlink in destination")
    if path.exists():
        return path
    temp = path.with_name(path.name + ".partial")
    with archive.extractfile(member) as inp, temp.open("xb") as out:
        shutil.copyfileobj(inp, out)
    temp.chmod(mode)
    os.chown(temp, user, user)
    temp.rename(path)
    return path


def restore_sources(source):
    manifest_path = source / "verified-local-members.json"
    if sha(manifest_path) != INDEX:
        raise ValueError("Unknown off-host FG custody")
    for name, row in json.loads(manifest_path.read_bytes()).items():
        p = source / name
        if p.name != name or p.stat().st_size != row["bytes"] or sha(p) != row["sha256"]:
            raise ValueError("Sealed member differs: " + name)
    runtime = json.loads((source / "runtime-members.json").read_bytes())
    pending = set(runtime)
    RUNTIME.mkdir(exist_ok=True)
    with tarfile.open(source / "runtime.tar.gz", "r|gz") as archive:
        for member in archive:
            expected = runtime[member.name]
            pending.remove(member.name)
            p = write_object(archive, member, RUNTIME, member.mode, 0)
            if [p.stat().st_size, sha(p), member.mode] != expected:
                raise ValueError("Effective code differs: " + member.name)
    if pending or {p.relative_to(RUNTIME).as_posix() for p in RUNTIME.rglob("*") if p.is_file()} != runtime.keys():
        raise ValueError("Effective file set differs")
    for folder in (WORK, WORK / "data", WORK / "data/filestore", STORE):
        folder.mkdir(mode=0o750, exist_ok=True)
        os.chown(folder, 61018, 61018)
    physical = json.loads((source / "filestore-physical.json").read_bytes())
    rows = {}
    for filename in ("filestore.tar", "filestore-extra.tar"):
        with tarfile.open(source / filename, "r|") as archive:
            for member in archive:
                if member.name in rows or not re.fullmatch(r"(?:checklist/)?[0-9a-f]{2}/[0-9a-f]{40}", member.name):
                    raise ValueError("Unexpected filestore member")
                obj = write_object(archive, member, STORE, 0o600, 61018)
                for folder in obj.parents:
                    if folder == STORE:
                        break
                    os.chown(folder, 61018, 61018)
                rows[member.name] = [obj.stat().st_size, sha(obj)]
    tree = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if len(rows) != physical["all_files"] or tree != physical["tree_sha256"]:
        raise ValueError("Restored source filestore differs")
    receipt = {"source_manifest": INDEX, "runtime_files": len(runtime), "physical_files": len(rows), "tree_sha256": tree}
    (WORK / "physical-source.json").write_text(json.dumps(receipt, sort_keys=True))
    print(json.dumps(receipt))


def pg(command, *args, **kwargs):
    launcher = Path(__file__).with_name("run_focal_print_command.py")
    return subprocess.run([sys.executable, str(launcher), "--user", "postgres", "--", command,
                           "-h", "/run/sys-55441", "-p", "55441", *args], check=True, **kwargs)


def start_cluster():
    runner = [sys.executable, str(Path(__file__).with_name("run_focal_print_command.py")), "--user", "postgres", "--"]
    local = ROOT / "work/sys-print-pg"
    socket = ROOT / "run/sys-55441"
    for directory, mode in ((local, 0o700), (socket, 0o755)):
        if directory.resolve() != directory:
            raise ValueError("Unexpected private cluster path")
        directory.mkdir(mode=mode, exist_ok=True)
        os.chown(directory, 61012, 61012)
    cluster = local / "cluster"
    dbargs = ["-D", "/work/sys-print-pg/cluster"]
    if not cluster.exists():
        subprocess.run([*runner, "initdb", *dbargs, "--encoding=UTF8", "--lc-collate=C", "--lc-ctype=C.UTF-8",
                        "--auth-local=peer", "--auth-host=reject"], check=True)
        custom = cluster / "sys-fixture.conf"
        custom.write_text("listen_addresses=''\nport=55441\nunix_socket_directories='/run/sys-55441'\n"
                          "jit=off\nshared_buffers=64MB\nmax_wal_size=128MB\nmin_wal_size=32MB\n")
        with (cluster / "postgresql.conf").open("a") as out:
            out.write("\ninclude 'sys-fixture.conf'\n")
    if (cluster / "PG_VERSION").read_text().strip() != "12":
        raise ValueError("Unexpected local PostgreSQL version")
    status = subprocess.run([*runner, "pg_ctl", *dbargs, "status"], capture_output=True)
    if status.returncode == 3:
        subprocess.run([*runner, "pg_ctl", *dbargs, "-w", "-l", "/work/sys-print-pg/postgres.log", "start"], check=True)
    elif status.returncode:
        raise ValueError("Could not identify the existing local cluster")
    print(pg("psql", "-XqAt", "-d", "postgres", "-c", "select version()", capture_output=True, text=True).stdout.strip())


def restore_sql(source):
    def query(db, sql):
        return pg("psql", "-XqAt", "-d", db, "-c", sql, capture_output=True, text=True).stdout.strip()
    if query("postgres", "select current_setting('port') || ':' || current_setting('data_directory')") != "55441:/work/sys-print-pg/cluster":
        raise ValueError("Expected the private SyS workstation cluster")
    if query("postgres", "select count(*) from pg_roles where rolname='odoo'") == "0":
        pg("createuser", "odoo")
    # The frozen database grants this role ACLs on 1,683 objects. It needs no login in QA.
    if query("postgres", "select count(*) from pg_roles where rolname='fcaror'") == "0":
        pg("createuser", "--no-login", "fcaror")
    if not query("postgres", "select 1 from pg_database where datname='" + DB + "'"):
        pg("createdb", "-T", "template0", "-O", "odoo", "-E", "UTF8", "--lc-collate=C", "--lc-ctype=C.UTF-8", DB)
    if not query(DB, "select to_regclass('public.ir_module_module')"):
        if query(DB, "select count(*) from pg_tables where schemaname='public'") != "0":
            raise ValueError("Private restore already contains application data")
        dump = source / "source.dump"
        if sha(dump) != "435bd9ba963688ce202107c1f63351080e55296ff25a4bdc1d23f2f0fb76bf83":
            raise ValueError("Unknown SQL snapshot")
        with dump.open("rb") as data:
            pg("pg_restore", "--no-tablespaces", "--exit-on-error", "--single-transaction", "-d", DB, stdin=data)
    print(query(DB, "select count(*) from ir_module_module where state='installed'"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("stage", choices=("sources", "cluster", "sql"))
    args = parser.parse_args()
    if args.stage == "cluster":
        start_cluster()
    else:
        (restore_sources if args.stage == "sources" else restore_sql)(args.source)
