"""Seal and boot a private restoration of an already converted SyS Community cohort."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tempfile

from custody_sys_previred_filestore import attachments, capture, digest, object_catalog, restore_objects
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import GIB, LOCK, require
from seal_converted_runtime import resolve_providers, seal


def full_snapshot(db):
    code = ("import json,sys\nsys.path.insert(0," + repr(str(Path(__file__).resolve().parent)) + ")\n"
            "from compare_sys_full_restore import snapshot\nprint(json.dumps(snapshot(" + repr(db) + ")))")
    result = subprocess.check_output(["sudo", "-n", "-u", "postgres", "python3", "-B", "-"], input=code.encode())
    return json.loads(result)


def verify_same(before, after):
    diff = {section: sorted(k for k in values.keys() | after[section].keys()
                            if values.get(k) != after[section].get(k)) for section, values in before.items()}
    require(not any(diff.values()), "full-restoration-drift: " + repr({k: v[:3] for k, v in diff.items() if v}))


def save(path, data):
    tmp = path.with_suffix(path.suffix + ".new")
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2))
    tmp.replace(path)


def check_modules(source):
    result = json.loads(query(source, """
        SELECT json_object_agg(name,json_build_array(latest_version,license)) FROM ir_module_module
         WHERE state='installed'
    """))
    require(result and "base" in result and "step_payroll_oca_api" in result and
            not any(value[1] == "OEEL-1" for value in result.values()), "converted-module-graph-required")
    return result


def package(args, out, source_db, modules):
    frozen = full_snapshot(source_db)
    final = out / "sealed"
    if final.exists():
        proof = json.loads((final / "backup.json").read_text())
        require(proof["source"] == source_db and proof["release_sha256"] == args.release_sha256, "backup-source-drift")
        original = json.loads(gzip.decompress((final / "source-snapshot.json.gz").read_bytes()))
        verify_same(original, frozen)
        for name, key in (("source.dump", "sql_sha256"), ("filestore.tar", "archive_sha256")):
            require(digest(final / name) == proof[key], "sealed-backup-checksum")
        require(digest(final / "runtime.tar.gz") == proof["runtime"]["archive_sha256"], "sealed-engine-checksum")
        return frozen, proof
    temporary = Path(tempfile.mkdtemp(prefix="capture-", dir=out))
    try:
        stored = attachments(source_db, query)
        catalog = object_catalog(stored.pop("references"))
        require(bool(catalog), "no-attachment-objects")
        source_store = args.source_data / "filestore" / source_db
        require(source_store.is_dir() and source_store.resolve() == source_store, "private-filestore-required")
        with (temporary / "source.dump").open("xb") as handle:
            pg("pg_dump", "-Fc", "--dbname=" + source_db, readonly=True, stdout=handle)
        filestore = capture(source_store, temporary, catalog)
        providers = resolve_providers(args.runtime, args.addons, args.source_data, modules)
        # A cold restore must reproduce the exact code that boots the converted source.
        # Some source manifests have an unapplied forward revision. Do not run an upgrade.
        changed = {k: {"database": v[0], "manifest": providers[k][1]} for k, v in modules.items()
                   if providers[k][1] != v[0]}
        for entry in changed.values():
            require(all(re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value) for value in entry.values()),
                    "unrecognized-provider-version")
            require(tuple(map(int, entry["manifest"].split("."))) >= tuple(map(int, entry["database"].split("."))),
                    "provider-is-older-than-converted-database")
        runtime = seal(args.runtime, providers, temporary)
        shutil.copyfile(args.release, temporary / "original-release.tar")
        require(digest(temporary / "original-release.tar") == args.release_sha256, "private-release-drift")
        shutil.copyfile(args.release.with_name("release-files.sha256"), temporary / "original-release-files.sha256")
        sets = {name: len(values) for name, values in frozen.items()}
        proof = dict(source=source_db, sql_sha256=digest(temporary / "source.dump"), sql_bytes=(temporary / "source.dump").stat().st_size,
                     release_sha256=args.release_sha256, counts=sets, rows=sum(v[0] for v in frozen["public_tables"].values()),
                     runtime=runtime, forward_manifests_on_source=changed, attachments=stored, **filestore)
        with gzip.open(temporary / "source-snapshot.json.gz", "wt") as handle:
            json.dump(frozen, handle, separators=(",", ":"), sort_keys=True)
        save(temporary / "backup.json", proof)
        temporary.rename(final)
        return frozen, proof
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def open_as_user(out, db, service):
    core = out / "sealed/runtime"
    args = [
        "unshare", "--net", "--", "sh", "-ec", 'ip link set dev lo up; exec "$@"', "steps",
        "sudo", "-n", "-u", service.pw_name, "env", "PYTHONDONTWRITEBYTECODE=1",
        "/usr/bin/python3.10", str(core / "odoo-bin"), "shell", "-c", "/etc/odoo18-sys.conf", "-d", db,
        "--db-filter=^" + db + "$", "--db_host=/var/run/postgresql", "--data-dir=" + str(out / "data"),
        "--addons-path=" + str(core / "addons") + "," + str(core / "odoo/addons"), "--no-http",
        "--workers=0", "--max-cron-threads=0", "--stop-after-init", "--load=base,web",
        "--logfile=" + str(out / "data/restore-odoo.log"),
    ]
    probe = """
import hashlib,json,sys
from pathlib import Path
import odoo
from odoo.modules.module import get_module_path
assert env.cr.dbname==expected_db
assert {l.split(':')[0].strip() for l in Path('/proc/net/dev').read_text().splitlines()[2:]}=={'lo'}
env.cr.rollback()
env.cr.execute('SET TRANSACTION READ ONLY')
core=Path(expected_core)
assert Path(odoo.__file__).resolve().is_relative_to(core)
installed=env['ir.module.module'].search([('state','=','installed')])
assert installed and not installed.filtered(lambda m:m.license=='OEEL-1')
assert all(Path(get_module_path(m.name)).resolve().is_relative_to(core) for m in installed)
actor=env['res.users'].browse(6)
assert actor.exists() and actor.active and not actor.share and not actor.has_group('base.group_system')
scope=env(user=actor.id,su=False,context={'allowed_company_ids':actor.company_ids.filtered('active').ids,'bin_size':False})
attachments=scope['ir.attachment'].search([('res_model','in',['res.company','ir.ui.menu','ir.ui.view']),
            ('res_field','not ilike','sign'),('store_fname','!=',False),('file_size','>',0),
            ('file_size','<',2000000)],order='id',limit=12)
assert attachments and not scope.su
for obj in attachments:
    obj.check_access('read')
    raw=obj.raw
    assert len(raw)==obj.file_size and hashlib.sha1(raw).hexdigest()==obj.checksum
print('CONVERTED_RESTORE='+json.dumps({'active':len(installed),'enterprise':0,'internal_uid':actor.id,
    'attachments_read':len(attachments),'models':sorted(set(attachments.mapped('res_model'))),
    'all_providers_inside_restored_capsule':True,'read_only':True}))
env.cr.rollback()
"""
    code = f"expected_db={db!r}\nexpected_core={str(core)!r}\n" + probe
    with (out / "orm.log").open("wb") as handle:
        run = subprocess.run(args, input=code.encode(), stdout=handle, stderr=handle)
    require(run.returncode == 0, "restored-official-orm-probe-failed")
    return json.loads(next(l.split("=", 1)[1] for l in (out / "orm.log").read_text().splitlines()
                           if l.startswith("CONVERTED_RESTORE=")))


def restore(args):
    source, target, space = args.source, args.target, args.tablespace
    require(re.fullmatch(r"COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]{1,25}", source) and
            re.fullmatch(r"COMMUNITY_SYS_PREVIRED_RECOVERY_[A-Z0-9_]{1,25}", target), "private-cohort-required")
    require(re.fullmatch(r"steps_community_storage_[0-9]{8}_community", space), "private-tablespace-required")
    out = args.output
    require(out.is_absolute() and out.parent.resolve() == out.parent and out.is_relative_to("/opt/steps-validation")
            and out.name == "recovery-" + target.lower(), "isolated-recovery-directory-required")
    require(args.source_data.is_relative_to("/opt/steps-validation") and
            args.release.is_relative_to("/opt/steps-validation") and digest(args.release) == args.release_sha256,
            "expected-private-release-required")
    owner, encoding, locale, ctype, size = json.loads(query("postgres", """
        SELECT json_build_array(pg_get_userbyid(datdba),pg_encoding_to_char(encoding),datcollate,datctype,
               pg_database_size(datname)) FROM pg_database WHERE datname='""" + source + "'"))
    require(owner == "odoo", "wrong-converted-owner")
    modules = check_modules(source)
    require(len(modules) == args.expected_active, "active-cohort-drift")
    service = pwd.getpwnam(owner)
    pgdir = Path(query("postgres", "SHOW data_directory"))
    tdir = Path(query("postgres", f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{space}'"))
    require(tdir.resolve().is_relative_to("/opt/steps-validation/community-payroll-storage-20261028") and
            shutil.disk_usage(tdir).free >= 5 * GIB + 3 * size and shutil.disk_usage(pgdir).free >= 5 * GIB,
            "private-disk-reserve-required")
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname IN ('{source}','{target}')") == "0",
            "private-source-or-target-in-use")
    if not out.exists():
        out.mkdir(mode=0o700)
        save(out / "identity.json", {"source": source, "target": target})
    require(not out.is_symlink() and json.loads((out / "identity.json").read_text()) == {"source": source, "target": target},
            "unrecognized-recovery-directory")
    frozen, proof = package(args, out, source, modules)
    sealed = out / "sealed"
    if not (out / "restore-start.json").is_file():
        require(query("postgres", f"SELECT count(*) FROM pg_database WHERE datname='{target}'") == "0", "target-already-exists")
        save(out / "restore-start.json", {"target": target, "dump": proof["sql_sha256"]})
    require(json.loads((out / "restore-start.json").read_text()) == {"target": target, "dump": proof["sql_sha256"]},
            "private-restore-identity-drift")
    if query("postgres", f"SELECT count(*) FROM pg_database WHERE datname='{target}'") == "0":
        pg("createdb", "--template=template0", "--owner=" + owner, "--tablespace=" + space, "--encoding=" + encoding,
           "--lc-collate=" + locale, "--lc-ctype=" + ctype, target)
    if query(target, "SELECT to_regclass('public.ir_module_module') IS NULL") == "t":
        require(query(target, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") == "0", "incomplete-target")
        with (sealed / "source.dump").open("rb") as handle, (out / "pg-restore.log").open("wb") as log:
            pg("pg_restore", "--exit-on-error", "--single-transaction", "--no-tablespaces", "--dbname=" + target,
               stdin=handle, stdout=log, stderr=log)
    require(query("postgres", f"SELECT s.spcname FROM pg_database d JOIN pg_tablespace s ON s.oid=d.dattablespace "
                              f"WHERE d.datname='{target}'") == space, "restore-tablespace-drift")
    verify_same(frozen, full_snapshot(target))
    catalog = object_catalog(attachments(target, query)["references"])
    data = out / "data"
    dest = data / "filestore" / target
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
            stage = Path(tmp) / "objects"
            stage.mkdir()
            restore_objects(sealed / "filestore.tar", stage, catalog)
            stage.rename(dest)
    require({p.relative_to(dest).as_posix() for p in dest.glob("*/*") if p.is_file()} == catalog.keys()
            and all((dest / n).stat().st_size == size and digest(dest / n, "sha1") == Path(n).name
                    for n, size in catalog.items()), "restored-filestore-drift")
    for directory in (out, sealed, sealed / "runtime", *(p for p in (sealed / "runtime").rglob("*") if p.is_dir())):
        os.chown(directory, 0, service.pw_gid)
        directory.chmod(0o750)
    for path in (data, *data.rglob("*")):
        require(not path.is_symlink(), "unexpected-restored-filestore-symlink")
        os.chown(path, service.pw_uid, service.pw_gid)
    orm = open_as_user(out, target, service)
    require(orm["active"] == len(modules) and check_modules(target) == modules, "restored-registry-drift")
    verify_same(frozen, full_snapshot(target))
    verify_same(frozen, full_snapshot(source))
    result = {**proof, "target": target, "tablespace": space, "full_post_boot_match": True,
              "source_unchanged": True, "role_probe": orm, "restored_filestore_objects": len(catalog)}
    save(out / "restore-proof.json", result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "target", "tablespace", "release-sha256"):
        parser.add_argument("--" + name, required=True)
    for name in ("output", "source-data", "runtime", "release"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--addons", type=Path, nargs="+", required=True)
    parser.add_argument("--expected-active", type=int, required=True)
    parsed = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore(parsed)
