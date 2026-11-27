"""Seal and independently restore the 193-module SyS SQL, effective code and physical files on WSL."""
import argparse
import ast
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

from restore_local_fiscal_print import DB as SOURCE, INDEX, ROOT, STORE, WORK, pg, sha, start_cluster

DB = "COMMUNITY_SYS_FINAL_RESTORED_20261127U46R"
MEM = Path("/dev/shm/sys-fg-193")
PORT = 55443
SOCKET = "/dev/shm/sys-fg-193/socket"
CODE = MEM / "tools"


def call(user, cmd, **kwargs):
    relay = Path(__file__).with_name("run_focal_print_command.py")
    return subprocess.run([sys.executable, str(relay), "--user", user, "--", *map(str, cmd)], check=True, **kwargs)


def psql(query, db=DB):
    args = ["psql", "-h", SOCKET, "-p", PORT, "-d", db, "-XqAt", "-v", "ON_ERROR_STOP=1", "-c", query]
    return call("postgres", args, capture_output=True, text=True).stdout.strip()


def save(path, value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    if path.suffix == ".gz":
        body = gzip.compress(body, mtime=0)
    if path.exists() and path.read_bytes() != body:
        raise ValueError("Existing evidence differs: " + path.name)
    path.write_bytes(body)


def prepare_snapshot_code():
    source = Path(__file__).resolve().parent
    CODE.mkdir(parents=True, mode=0o755, exist_ok=True)
    pending, done = {"compare_sys_full_restore", "guard_sys_original_catalogue"}, set()
    while pending:
        name = pending.pop()
        if name in done:
            continue
        path = source / (name + ".py")
        shutil.copyfile(path, CODE / path.name)
        done.add(name)
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node, ast.ImportFrom) and node.module and (source / (node.module + ".py")).is_file():
                pending.add(node.module)


def capture(db, host, port, directory):
    prepare_snapshot_code()
    command = ("import sys,json,psycopg2;sys.path.insert(0,'/dev/shm/sys-fg-193/tools');"
               "from compare_sys_full_restore import snapshot;from guard_sys_original_catalogue import SQL,digest;"
               "args=" + repr((db, host, port)) + ";db,sock,port=args;"
               "cx=psycopg2.connect(dbname=db,host=sock,port=port,user='postgres');cx.set_session(readonly=True);"
               "c=cx.cursor();c.execute('SET LOCAL search_path=pg_catalog,public');c.execute(SQL);"
               "print(json.dumps({'catalogue':digest(c.fetchone()[0]),'snapshot':snapshot(db,socket_dir=sock,port=port)}))")
    result = json.loads(call("postgres", ["python3.10", "-c", command], capture_output=True).stdout)
    if result["catalogue"] != "a2535d3213a101a03297564d282b0aa2a2f6940f2fbc5073a2b707c3797b2e4d":
        raise ValueError("Unexpected complete PostgreSQL catalogue")
    save(directory / "snapshot.json.gz", result)
    return result


def inventory(store):
    return {p.relative_to(store).as_posix(): [p.stat().st_size, sha(p)] for p in store.rglob("*") if p.is_file()}


def providers(custody):
    current = json.loads((custody / "effective-providers.json").read_bytes())
    result = {k: v[1:] for k, v in current.items()}
    result["step_report_print_colors"] = ["18.0.1.0.0", "LGPL-3"]
    return result


def seal(custody):
    if sha(custody / "verified-local-members.json") != INDEX:
        raise ValueError("The independently verified predecessor is required")
    MEM.mkdir(mode=0o711, exist_ok=True)
    output = MEM / "sealed"
    output.mkdir(mode=0o700, exist_ok=True)
    if (output / "release.json").exists():
        verify(output, custody)
        return
    start_cluster()
    before = capture(SOURCE, "/run/sys-55441", 55441, output)
    expected = providers(custody)
    sql = "SELECT json_object_agg(name,json_build_array(latest_version,license)) FROM ir_module_module WHERE state='installed'"
    if json.loads(pg("psql", "-XtA", "-d", SOURCE, "-c", sql, capture_output=True).stdout) != expected:
        raise ValueError("Unknown source module versions or licenses")
    dump = output / "source.dump"
    if not dump.exists():
        partial = dump.with_suffix(".partial")
        with partial.open("xb") as out:
            call("postgres", ["pg_dump", "-h", "/run/sys-55441", "-p", "55441", "--serializable-deferrable",
                              "-Fc", "-d", SOURCE], stdout=out)
        partial.rename(dump)
    original = set()
    for name in ("filestore.tar", "filestore-extra.tar"):
        with tarfile.open(custody / name, "r|") as archive:
            original.update(m.name for m in archive)
    current = inventory(STORE)
    if len(original) != 2702 or len(current) != 2708 or not original <= current.keys():
        raise ValueError("Unexpected physical source graph")
    save(output / "filestore.json.gz", current)
    delta = output / "filestore-delta.tar"
    if not delta.exists():
        with tarfile.open(delta, "x") as archive:
            for name in sorted(current.keys() - original):
                content = (STORE / name).read_bytes()
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(content), 0o600
                archive.addfile(member, io.BytesIO(content))
    shutil.copyfile(WORK / "colors.tar", output / "print.tar")
    save(output / "providers.json", expected)
    if before != capture(SOURCE, "/run/sys-55441", 55441, output):
        raise ValueError("The source changed during capture")
    release = {"source": SOURCE, "target": DB, "modules": len(expected),
               "rows": sum(t[0] for t in before["snapshot"]["public_tables"].values()), "source_index": INDEX,
               "base_members": {k: sha(custody / k) for k in ("runtime.tar.gz", "runtime-members.json",
                                "filestore.tar", "filestore-extra.tar", "effective-providers.json")},
               "files": {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}}
    save(output / "release.json", release)
    verify(output, custody)
    print("SEALED", sha(output / "release.json"), release["rows"], release["modules"])


def verify(sealed, custody):
    release = json.loads((sealed / "release.json").read_bytes())
    if release["source_index"] != INDEX or sha(custody / "verified-local-members.json") != INDEX:
        raise ValueError("Unknown immutable custody")
    if release["target"] != DB or release["source"] != SOURCE or release["modules"] != 193:
        raise ValueError("Unknown product scope")
    for folder, kind in ((sealed, "files"), (custody, "base_members")):
        for name, expected in release[kind].items():
            if Path(name).name != name or sha(folder / name) != expected:
                raise ValueError("Unexpected archive bytes: " + name)
    if sha(sealed / "print.tar") != "db1f4c20809563d81e759b2d03c76b1ed57f547d02e4b320eca7901f4cc19dc9":
        raise ValueError("Unknown print extension")
    return release


def restore(custody, sealed):
    release = verify(sealed, custody)
    if os.path.ismount("/dev/shm") is False or shutil.disk_usage("/dev/shm").free < 1000 * 1024**2:
        raise ValueError("Dedicated WSL memory capacity required")
    for directory, uid, mode in ((MEM / "postgres", 61012, 0o700), (Path(SOCKET), 61012, 0o755),
                                 (MEM / "data", 61018, 0o700), (MEM / "proofs", 0, 0o700)):
        directory.mkdir(mode=mode, exist_ok=True)
        os.chown(directory, uid, uid)
    cluster = MEM / "postgres/cluster"
    if not cluster.exists():
        call("postgres", ["initdb", "-D", cluster, "--encoding=UTF8", "--lc-collate=C", "--lc-ctype=C.UTF-8",
                          "--auth-local=peer", "--auth-host=reject"], stdout=subprocess.DEVNULL)
        with (cluster / "postgresql.conf").open("a") as out:
            out.write("\nlisten_addresses=''\nport=55443\nunix_socket_directories='" + SOCKET + "'\n"
                      "jit=off\nshared_buffers=64MB\nmax_wal_size=128MB\nmin_wal_size=32MB\n")
    if not (cluster / "postmaster.pid").exists():
        call("postgres", ["pg_ctl", "-D", cluster, "-w", "-l", MEM / "postgres/postgres.log", "start"])
    if psql("SHOW data_directory", "postgres") != str(cluster):
        raise ValueError("Wrong private PostgreSQL instance")
    for role in ("odoo", "fcaror"):
        if not psql("SELECT 1 FROM pg_roles WHERE rolname='" + role + "'", "postgres"):
            call("postgres", ["createuser", "-h", SOCKET, "-p", PORT, "--login" if role == "odoo" else "--no-login", role])
    if not psql("SELECT 1 FROM pg_database WHERE datname='" + DB + "'", "postgres"):
        call("postgres", ["createdb", "-h", SOCKET, "-p", PORT, "-T", "template0", "-O", "odoo", "-E", "UTF8",
                          "--lc-collate=C", "--lc-ctype=C.UTF-8", DB])
    if not psql("SELECT to_regclass('public.ir_module_module')"):
        if psql("SELECT count(*) FROM pg_tables WHERE schemaname='public'") != "0":
            raise ValueError("The new product must start empty")
        with (sealed / "source.dump").open("rb") as dump:
            call("postgres", ["pg_restore", "-h", SOCKET, "-p", PORT, "--no-tablespaces", "--single-transaction",
                              "--exit-on-error", "-d", DB], stdin=dump)
    restored = capture(DB, SOCKET, PORT, MEM / "proofs")
    if restored != json.loads(gzip.decompress((sealed / "snapshot.json.gz").read_bytes())):
        raise ValueError("Restored rows, sequences or schema differ")
    print("SQL", release["rows"], release["modules"])
    physical = json.loads(gzip.decompress((sealed / "filestore.json.gz").read_bytes()))
    store = MEM / "data/filestore" / DB
    for file in (custody / "filestore.tar", custody / "filestore-extra.tar", sealed / "filestore-delta.tar"):
        with tarfile.open(file, "r|") as archive:
            for member in archive:
                if (not member.isfile() or member.name not in physical or not
                        re.fullmatch(r"(?:checklist/)?[a-f0-9]{2}/[a-f0-9]{40}", member.name)):
                    raise ValueError("Unknown physical member")
                obj = store / member.name
                obj.parent.mkdir(parents=True, exist_ok=True)
                if not obj.exists():
                    with archive.extractfile(member) as inp, obj.open("xb") as out:
                        shutil.copyfileobj(inp, out)
                    obj.chmod(0o600)
                    os.chown(obj, 61018, 61018)
    if inventory(store) != physical:
        raise ValueError("Restored original objects and markers differ")
    for base, dirs, _ in os.walk(MEM / "data"):
        os.chown(base, 61018, 61018)
    # The code is mounted read-only by ownership. Recheck every byte and mode before the first boot.
    runtime = json.loads((custody / "runtime-members.json").read_bytes())
    base = ROOT / "work/sys-fg-code"
    paths = {p.relative_to(base).as_posix(): p for p in base.rglob("*") if p.is_file()}
    if (paths.keys() != runtime.keys() or any(p.is_symlink() or p.stat().st_uid or
            [p.stat().st_size, sha(p), p.stat().st_mode & 0o777] != runtime[name] for name, p in paths.items())):
        raise ValueError("Shared runtime differs from the sealed source")
    overlay = MEM / "overlay"
    with tarfile.open(sealed / "print.tar") as archive:
        for member in archive:
            if not member.isfile() or Path(member.name).is_absolute() or ".." in Path(member.name).parts:
                raise ValueError("Invalid print module member")
            p = overlay / member.name
            p.parent.mkdir(parents=True, exist_ok=True)
            data = archive.extractfile(member).read()
            if p.exists() and p.read_bytes() != data:
                raise ValueError("Different restored print extension")
            p.write_bytes(data)
            p.chmod(0o644)
    save(MEM / "proofs/restored.json", {"release_sha256": sha(sealed/"release.json"), "rows": release["rows"],
         "modules": 193, "tables": len(restored["snapshot"]["public_tables"]), "runtime_files": len(paths) + 3,
         "original_counters": len(restored["snapshot"]["sequence_values"]), "physical": len(physical),
         "catalogue": restored["catalogue"]})
    print("PHYSICAL", len(physical), len(paths) + 3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("seal", "restore"))
    parser.add_argument("custody", type=Path)
    parser.add_argument("--sealed", type=Path, default=MEM / "sealed")
    args = parser.parse_args()
    (seal(args.custody) if args.stage == "seal" else restore(args.custody, args.sealed))
