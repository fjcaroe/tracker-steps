"""Restore the exact 162-module Steps support product into the reserved private integration database."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tarfile
import tempfile

from admit_steps_sales_documents import odoo
from admit_steps_support_portal import RECOVERY, WORK
from audit_steps_sales_schema import objects
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from restore_converted_sys_cohort import check_modules, full_snapshot, save, verify_same
from restore_native_product_backup import pg, query
from restore_steps_sales_backup import BASE, SPACE
from restore_sys_previred_pair import GIB, LOCK, require
from seal_converted_runtime import extract_runtime
from verify_converted_sql_schema import schema
from verify_steps_support_backup import PACKAGES, SOURCE, SUCCESSOR, compressed, verify


OUTPUT = BASE / "steps-integrated-20261127U46A"


def set_directories(tree, group):
    for path in [tree, *(p for p in tree.rglob("*") if p.is_dir())]:
        require(not path.is_symlink(), "unsafe-private-directory")
        os.chown(path, 0, group)
        path.chmod(0o750)


def code(base, sealed, user):
    members = json.loads((base / "runtime-members.json").read_bytes())
    runtime = OUTPUT / "runtime"
    if not runtime.exists():
        with tempfile.TemporaryDirectory(dir=OUTPUT) as tmp:
            stage = Path(tmp) / "runtime"
            cached = base / "runtime"
            if cached.is_dir():
                # The sealed, independently hashed R extraction can share immutable file inodes.
                stage.mkdir()
                for name, (size, sha, mode) in members.items():
                    source = cached / name
                    require(source.resolve() == source and digest(source) == sha and source.stat().st_size == size
                            and source.stat().st_mode & 0o777 == mode, "cached-Community-source-drift")
                    dest = stage / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    os.link(source, dest)
            else:
                extract_runtime(base / "runtime.tar.gz", stage, members)
            set_directories(stage, user.pw_gid)
            stage.rename(runtime)
    require({p.relative_to(runtime).as_posix() for p in runtime.rglob("*") if p.is_file()} == members.keys() and
            all((runtime / n).resolve() == runtime / n and digest(runtime / n) == v[1] and
                (runtime / n).stat().st_mode & 0o777 == v[2] for n, v in members.items()), "restored-runtime-drift")
    overlay = OUTPUT / "addons"
    overlay.mkdir(exist_ok=True)
    checked = set()
    for name in PACKAGES:
        with tarfile.open(sealed / (name + ".tar")) as archive:
            for member in archive:
                dest = overlay / member.name
                require(member.isfile() and dest.resolve().is_relative_to(overlay) and dest not in checked,
                        "unsafe-support-module")
                checked.add(dest)
                payload = archive.extractfile(member).read()
                dest.parent.mkdir(exist_ok=True, parents=True)
                if not dest.exists():
                    with dest.open("xb") as out:
                        out.write(payload)
                    dest.chmod(0o644)
                require(dest.resolve() == dest and payload == dest.read_bytes(), "restored-support-code-drift")
    require({p for p in overlay.rglob("*") if p.is_file()} == checked, "unexpected-support-files")
    set_directories(overlay, user.pw_gid)
    command = odoo(True, work=OUTPUT, target=SUCCESSOR)
    command[command.index(next(a for a in command if a.endswith("/odoo-bin")))] = str(runtime / "odoo-bin")
    command[command.index(next(a for a in command if a.startswith("--addons-path=")))] = "--addons-path=" + ",".join(
        map(str, [overlay, runtime / "addons", runtime / "odoo/addons"]))
    save(OUTPUT / "private-args.json", command)
    return command


def restore(base_root, sealed, sha):
    require(OUTPUT.parent == BASE and OUTPUT.resolve() == OUTPUT and
            all(p.resolve(strict=True) == p and p.is_relative_to(BASE) for p in (base_root, sealed)),
            "isolated-restoration-path-required")
    proof = verify(base_root, sealed, sha)
    base = base_root / "sealed" if (base_root / "sealed").is_dir() else base_root
    volume = Path(query("postgres", f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{SPACE}'"))
    require(volume.resolve(strict=True).is_relative_to(BASE / "community-payroll-storage-20261028"),
            "unrecognized-private-tablespace")
    tree = compressed(sealed, "filestore.json.gz")
    exists = query("postgres", f"SELECT count(*) FROM pg_database WHERE datname='{SUCCESSOR}'") == "1"
    marker = OUTPUT / "identity.json"
    identity = {"database": SUCCESSOR, "checkpoint_sha256": sha, "tablespace": SPACE}
    require(not exists or (marker.is_file() and json.loads(marker.read_bytes()) == identity),
            "unused-or-identified-integration-database-required")
    restored = exists and query(SUCCESSOR, "SELECT to_regclass('public.ir_module_module') IS NOT NULL") == "t"
    dest = OUTPUT / "data/filestore" / SUCCESSOR
    reserve = ((0 if dest.is_dir() else sum(v[0] for v in tree.values()))
               + (0 if restored else (sealed / "source.dump").stat().st_size * 14)
               + (0 if (base / "runtime").is_dir() else sum(v[0] for v in json.loads(
                   (base / "runtime-members.json").read_bytes()).values())))
    # Count only already allocated contiguous future WAL segments on the current timeline.
    wal = json.loads(query("postgres", """SELECT json_build_array(
        pg_walfile_name(pg_current_wal_insert_lsn()), pg_size_bytes(current_setting('wal_segment_size')),
        (SELECT json_agg(name) FROM pg_ls_waldir() WHERE name ~ '^[0-9A-F]{24}$'))"""))
    current, segment, names = wal
    names = set(names)
    future = 0
    per_log = 2 ** 32 // segment
    first = int(current[8:16], 16) * per_log + int(current[16:], 16)
    while True:
        high, low = divmod(first + future + 1, per_log)
        if f"{current[:8]}{high:08X}{low:08X}" not in names:
            break
        future += 1
    db_bytes = int(query("postgres", f"""SELECT COALESCE((SELECT pg_database_size(oid) FROM pg_database
        WHERE datname='{SOURCE}'),{(sealed / "source.dump").stat().st_size * 14})"""))
    main = Path(query("postgres", "SHOW data_directory"))
    wal_growth = max(0, (0 if restored else 2 * db_bytes) + 2 * segment - future * segment)
    space = {"volume_free": shutil.disk_usage(volume).free, "database_free": shutil.disk_usage(main).free,
             "volume_growth_estimate": reserve, "WAL_growth_estimate": wal_growth,
             "future_WAL_segments": future, "floor_each": 5 * GIB}
    require(space["volume_free"] - reserve >= 5 * GIB and space["database_free"] - wal_growth >= 5 * GIB,
            "reserve-for-private-integration:" + json.dumps(space))
    user = pwd.getpwnam("odoo")
    OUTPUT.mkdir(exist_ok=True)
    os.chown(OUTPUT, 0, user.pw_gid)
    OUTPUT.chmod(0o750)
    if not marker.exists():
        require(not exists, "unused-integration-database-required")
        save(marker, identity)
    require(json.loads(marker.read_bytes()) == identity, "integration-database-identity-drift")
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname='{SUCCESSOR}'") == "0",
            "integration-database-in-use")
    if not exists:
        pg("createdb", "--template=template0", "--owner=odoo", "--tablespace=" + SPACE,
           "--encoding=UTF8", "--lc-collate=C", "--lc-ctype=C.UTF-8", SUCCESSOR)
    placement = query("postgres", f"""SELECT pg_get_userbyid(datdba)||'/'||spcname FROM pg_database
        JOIN pg_tablespace ON dattablespace=pg_tablespace.oid WHERE datname='{SUCCESSOR}'""")
    require(placement == "odoo/" + SPACE, "restored-database-location-drift")
    if query(SUCCESSOR, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") == "0":
        with (sealed / "source.dump").open("rb") as src, (OUTPUT / "pg-restore.log").open("ab") as log:
            pg("pg_restore", "--no-tablespaces", "--single-transaction", "--exit-on-error", "-d", SUCCESSOR,
               stdin=src, stdout=log, stderr=log)
    snap = compressed(sealed, "snapshot.json.gz")
    verify_same(snap, full_snapshot(SUCCESSOR))
    require(objects(SUCCESSOR) == compressed(sealed, "sql-objects.json.gz"), "restored-index-or-view-drift")
    require(schema(pg("pg_dump", "--schema-only", "--no-tablespaces", SUCCESSOR, readonly=True,
                      stdout=subprocess.PIPE).stdout) == proof["schema_sha256"], "restored-SQL-schema-drift")
    catalog = object_catalog(attachments(SUCCESSOR, query)["references"])
    dest.parent.mkdir(exist_ok=True, parents=True)
    if not dest.exists():
        with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
            stage = Path(tmp) / "store"
            stage.mkdir()
            verify(base_root, sealed, sha, stage)
            stage.rename(dest)
    require(inventory(dest, catalog) == tree, "restored-physical-tree-drift")
    for item in [OUTPUT / "data", *(OUTPUT / "data").rglob("*")]:
        require(not item.is_symlink(), "unsafe-restored-data")
        os.chown(item, user.pw_uid, user.pw_gid)
    command = code(base, sealed, user)
    active = json.loads((sealed / "providers.json").read_bytes())
    probe = Path(__file__).with_name("probe_steps_support_thread.py").read_text()
    script = probe + """
from odoo.modules import module
for name, (version, license) in active.items():
    manifest = module.get_manifest(name)
    assert [manifest['version'], manifest['license']] == [version, license]
    provider = Path(module.get_module_path(name)).resolve(strict=True)
    if name in support:
        expected = root / 'addons' / name
    elif name == 'base':
        expected = root / 'runtime/odoo/addons/base'
    else:
        expected = root / 'runtime/addons' / name
    assert provider == expected
print('RESTORED_THREAD='+json.dumps(run(env), sort_keys=True))
"""
    script = "from pathlib import Path\nroot=Path(" + repr(str(OUTPUT)) + ")\nactive=" + repr(active) + (
        "\nsupport=" + repr(sorted(PACKAGES)) + "\n") + script
    accepted = json.loads((sealed / "acceptance.json").read_bytes())
    first = None
    for number in (1, 2):
        process = subprocess.run(command, input=script.encode(), capture_output=True)
        (OUTPUT / f"boot-{number}.log").write_bytes(process.stdout + process.stderr)
        process.check_returncode()
        (result,) = [json.loads(row.split(b"=", 1)[1]) for row in process.stdout.splitlines()
                     if row.startswith(b"RESTORED_THREAD=")]
        require(result["operators"] == [accepted["original_chatter"]] * 2 and
                result["portal"]["invited_threads"] == accepted["http"]["tickets"] and
                result["portal"]["attachment_bytes"] == accepted["http"]["attachment_bytes"] and
                result["portal"]["messages"] == accepted["http"]["messages"] and
                result["portal"]["attachment_values_sha256"] ==
                "48771f873bf441b655f4509e52498d4cda9d512839e2b47ec6f7f9b6a65dc11c" and
                result["portal"]["thread_values_sha256"] ==
                "7f8e2907bfe583f29eec9beb633fb201d5d888032d33c0599833e5f0a67f1e4e" and
                result["portal"]["public_attachment_record_denials"] == accepted["http"]["attachments"],
                "restored-actor-or-attachment-drift")
        require(first is None or result == first, "second-boot-differs")
        first = result
        require(check_modules(SUCCESSOR) == active and inventory(dest, catalog) == tree,
                "post-boot-source-or-filestore-drift")
        verify_same(snap, full_snapshot(SUCCESSOR))
    space.update(final_volume_free=shutil.disk_usage(volume).free, final_database_free=shutil.disk_usage(main).free)
    require(min(space["final_volume_free"], space["final_database_free"]) >= 5 * GIB, "final-free-space-reserve")
    receipt = {**proof, "restored": SUCCESSOR, "checked_boots": 2, "thread": first, "free_space": space}
    save(OUTPUT / "restore-proof.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=RECOVERY)
    parser.add_argument("--checkpoint", type=Path, default=WORK / "final-checkpoint")
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        print(json.dumps(restore(args.base, args.checkpoint, args.sha256), indent=2))
