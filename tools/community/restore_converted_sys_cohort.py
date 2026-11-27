"""Seal and boot a private restoration of an already converted SyS Community cohort."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tempfile
import tarfile
from collections import Counter

from converted_cohort_profile import converted_profile
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


def source_sequence_advances(stored, current, allowed):
    if not allowed:
        verify_same(stored, current)
        return {}
    historical = stored["sequence_values"]
    observed = current["sequence_values"]
    require(historical.keys() == observed.keys(), "live-sequence-inventory-drift")
    verify_same(stored, {**current, "sequence_values": historical})
    changes = {}
    for name, before in historical.items():
        after = observed[name]
        if before == after:
            continue
        definition = stored["sequence_definitions"][name]
        require(definition[4] > 0 and not definition[5] and after[1] and after[0] >= before[0],
                "nonmonotonic-live-control-sequence")
        changes[name] = {"frozen": before, "live": after}
    return changes


def save(path, data):
    tmp = path.with_suffix(path.suffix + ".new")
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2))
    tmp.replace(path)


def check_modules(source):
    result = json.loads(query(source, """
        SELECT json_object_agg(name,json_build_array(latest_version,license)) FROM ir_module_module
         WHERE state='installed'
    """))
    anchor = "crm" if source.startswith("COMMUNITY_STEPS_CRM_") else "step_payroll_oca_api"
    require(result and "base" in result and anchor in result and
            not any(value[1] == "OEEL-1" for value in result.values()), "converted-module-graph-required")
    return result


def check_cerro_release(release, origin):
    """Check exactly the eight original U42F provider files before capturing executable code."""
    expected = {}
    with tarfile.open(release, "r:") as archive:
        for member in archive:
            parts = Path(member.name)
            require(member.isfile() and parts.parts[0] == "step_payroll_engine_transition" and
                    not parts.is_absolute() and ".." not in parts.parts, "unexpected-review-package-member")
            name = Path(*parts.parts[1:])
            require(name not in expected, "duplicate-reviewed-provider-file")
            with archive.extractfile(member) as archived:
                expected[name] = hashlib.sha256(archived.read()).hexdigest()
    actual = {p.relative_to(origin): digest(p) for p in origin.rglob("*") if p.is_file()
              and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")}
    require(len(expected) == 8 and actual == expected, "reviewed-provider-differs-from-original-release")
    manifest = {name.as_posix(): value for name, value in actual.items()}
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def package(args, out, source_db, modules):
    frozen = full_snapshot(source_db)
    final = out / "sealed"
    if final.exists():
        proof = json.loads((final / "backup.json").read_text())
        require(proof["source"] == source_db and proof["release_sha256"] == args.release_sha256, "backup-source-drift")
        original = json.loads(gzip.decompress((final / "source-snapshot.json.gz").read_bytes()))
        changes = source_sequence_advances(original, frozen, args.allow_forward_sequences_on_source)
        for name, key in (("source.dump", "sql_sha256"), ("filestore.tar", "archive_sha256")):
            require(digest(final / name) == proof[key], "sealed-backup-checksum")
        require(digest(final / "runtime.tar.gz") == proof["runtime"]["archive_sha256"], "sealed-engine-checksum")
        return original, proof, frozen, changes
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
        for name, entry in changed.items():
            require(all(re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value) for value in entry.values()),
                    "unrecognized-provider-version")
            require(tuple(map(int, entry["manifest"].split("."))) >= tuple(map(int, entry["database"].split("."))),
                    "provider-is-older-than-converted-database")
            entry["provider"] = "official Community" if Path(providers[name][0]).is_relative_to(args.runtime.resolve()) else "cohort addon"
        db_licenses = dict(Counter(v[1] for v in modules.values()))
        source_licenses = dict(Counter(v[2] for v in providers.values()))
        review_map = None
        product = converted_profile(source_db, args.target)
        if product == "steps":
            from prepare_steps_crm_cohort import digest as inventory_digest, FREE, SOURCE_MANIFESTS
            integrated = (source_db,args.target) == ('COMMUNITY_STEPS_CRM_DOC_20261127U44P','COMMUNITY_STEPS_CRM_RECOVERY_20261127U44R')
            expected_count = 160 if integrated else 157
            expected_digest = 'aaf242c83be6f9d1a2efd3da47e4dcb04e250376103334a04388a97c4bf9346f' if integrated else SOURCE_MANIFESTS
            require(not changed and len(modules) == expected_count and set(db_licenses) | set(source_licenses) <= FREE
                    and all(modules[name][1] == provider[2] for name, provider in providers.items()),
                    "unexpected-steps-providers")
            actual = {name: digest(Path(entry[0]) / "__manifest__.py") for name, entry in providers.items()}
            require(inventory_digest(actual) == expected_digest, "original-steps-provider-manifests-required")
        if product == "cerro":
            require(set(db_licenses) | set(source_licenses) <= {"LGPL-3", "AGPL-3", "GPL-3"},
                    "expected-free-cerro-provider-licenses")
            review_map = check_cerro_release(args.release, Path(providers["step_payroll_engine_transition"][0]))
            require(review_map == "95ad05120c3a317c4139e43d664f270ed6ae69f4beb7a8d9cb890bbf910e759a",
                    "reviewed-provider-map-differs")
        runtime = seal(args.runtime, providers, temporary)
        shutil.copyfile(args.release, temporary / "original-release.tar")
        require(digest(temporary / "original-release.tar") == args.release_sha256, "private-release-drift")
        shutil.copyfile(args.release.with_name("release-files.sha256"), temporary / "original-release-files.sha256")
        sets = {name: len(values) for name, values in frozen.items()}
        proof = dict(source=source_db, sql_sha256=digest(temporary / "source.dump"), sql_bytes=(temporary / "source.dump").stat().st_size,
                     release_sha256=args.release_sha256, database_licenses=db_licenses, effective_licenses=source_licenses,
                     counts=sets, rows=sum(v[0] for v in frozen["public_tables"].values()),
                     runtime=runtime, forward_manifests_on_source=changed, attachments=stored, **filestore)
        if review_map:
            proof["contract_provider_file_map_sha256"] = review_map
        if product in ("cerro", "steps"):
            proof["simultaneous_physical_tree_sha256"] = args.physical_tree_sha256
        with gzip.open(temporary / "source-snapshot.json.gz", "wt") as handle:
            json.dump(frozen, handle, separators=(",", ":"), sort_keys=True)
        save(temporary / "backup.json", proof)
        temporary.rename(final)
        return frozen, proof, frozen, {}
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def open_as_user(out, db, service, boot, hidden_sources, *, private_server=False):
    core = out / "sealed/runtime"
    scratch = out / "data/tmp"
    scratch.mkdir(mode=0o700, exist_ok=True)
    os.chown(scratch, service.pw_uid, service.pw_gid)
    cerro = db.startswith("COMMUNITY_CERRO_PAYROLL_RECOVERY_")
    steps = db.startswith("COMMUNITY_STEPS_CRM_RECOVERY_")
    config = "/etc/odoo18.conf" if steps else "/etc/dev_odoo18.conf" if cerro else "/etc/odoo18-sys.conf"
    mounts = [] if private_server else [
        "bwrap", "--die-with-parent", "--ro-bind", "/", "/", "--tmpfs", "/opt/steps-validation",
        "--tmpfs", "/srv/odoo-data/steps-anchor-validation", "--tmpfs", "/opt/odoo18",
        "--tmpfs", "/opt/steps-managed", "--tmpfs", "/opt/luis_odoo18",
        "--dir", str(out.parent), "--ro-bind", str(out), str(out),
        "--bind", str(out / "data"), str(out / "data"), "--proc", "/proc", "--dev-bind", "/dev", "/dev", "--"]
    args = [
        "unshare", "--net", "--", "sh", "-ec", 'ip link set dev lo up; exec "$@"', "steps", *mounts,
        "sudo", "-n", "-u", service.pw_name, "env", "PYTHONDONTWRITEBYTECODE=1", "TMPDIR=" + str(scratch),
        "/usr/bin/python3.10", str(core / "odoo-bin"), "shell", "-c", config, "-d", db,
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
assert all(not Path(p).exists() for p in expected_hidden)
assert Path(odoo.__file__).resolve().is_relative_to(core)
installed=env['ir.module.module'].search([('state','=','installed')])
assert installed and not installed.filtered(lambda m:m.license=='OEEL-1')
assert all(Path(get_module_path(m.name)).resolve().is_relative_to(core) for m in installed)
if is_steps:
    actor, extra = steps_restore_access(env, core)
elif is_cerro:
    actor,extra=cerro_restore_access(env)
else:
    actor=env['res.users'].browse(6)
    assert actor.exists() and actor.active and not actor.share and actor.has_group('payroll.group_payroll_manager')
    extra={'payroll_pdf':restricted_attachment(env,actor)}
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
    'original_settings_group':actor.has_group('base.group_system'),'superuser':scope.su,
    'attachments_read':len(attachments),'models':sorted(set(attachments.mapped('res_model'))),
    'all_providers_inside_restored_capsule':True,'source_directories_hidden':True,'read_only':True,**extra}))
env.cr.rollback()
"""
    probes = ["probe_converted_cohort_attachment.py"]
    if cerro:
        probes = ["probe_converted_cerro_access.py"]
    if steps:
        probes = ["probe_steps_crm_pipeline.py", "probe_converted_steps_access.py"]
        if db == 'COMMUNITY_STEPS_CRM_RECOVERY_20261127U44R':
            probes.append('probe_steps_sales_library.py')
    role_probe = "\n".join(Path(__file__).with_name(name).read_text() for name in probes)
    code = role_probe + "\n" + f"is_cerro={cerro!r}\nis_steps={steps!r}\nexpected_db={db!r}\nexpected_core={str(core)!r}\nexpected_hidden={list(map(str, hidden_sources))!r}\n" + probe
    with (out / f"orm-{boot}.log").open("wb") as handle:
        run = subprocess.run(args, input=code.encode(), stdout=handle, stderr=handle)
    require(run.returncode == 0, "restored-official-orm-probe-failed")
    return json.loads(next(l.split("=", 1)[1] for l in (out / f"orm-{boot}.log").read_text().splitlines()
                           if l.startswith("CONVERTED_RESTORE=")))


def restore(args):
    source, target, space = args.source, args.target, args.tablespace
    product = converted_profile(source, target)
    suffix = "cerro" if product == "cerro" else "community"
    require(re.fullmatch(r"steps_community_storage_[0-9]{8}_" + suffix, space), "private-tablespace-required")
    out = args.output
    require(out.is_absolute() and out.parent.resolve() == out.parent and out.is_relative_to("/opt/steps-validation")
            and out.name == "recovery-" + target.lower(), "isolated-recovery-directory-required")
    require(args.source_data.is_relative_to("/opt/steps-validation") and
            args.release.is_relative_to("/opt/steps-validation") and digest(args.release) == args.release_sha256,
            "expected-private-release-required")
    owner, encoding, locale, ctype, size = json.loads(query("postgres", """
        SELECT json_build_array(pg_get_userbyid(datdba),pg_encoding_to_char(encoding),datcollate,datctype,
               pg_database_size(datname)) FROM pg_database WHERE datname='""" + source + "'"))
    require(owner == ("dev_odoo18" if product == "cerro" else "odoo"), "wrong-converted-owner")
    modules = check_modules(source)
    require(len(modules) == args.expected_active, "active-cohort-drift")
    service = pwd.getpwnam("odoo")
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
    if product in ("cerro", "steps"):
        from complete_converted_filestore import inventory

        original_objects = object_catalog(attachments(source, query)["references"])
        physical = inventory(args.source_data / "filestore" / source, original_objects)
        args.physical_tree_sha256 = hashlib.sha256(
            json.dumps(physical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    frozen, proof, source_at_start, advances = package(args, out, source, modules)
    if product in ("cerro", "steps"):
        require(proof.get("simultaneous_physical_tree_sha256") == args.physical_tree_sha256,
                "physical-source-changed-since-the-sql-freeze")
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
    check_replay, view_replay = {}, {}
    if product == "cerro":
        checker = Path(__file__).with_name("restore_original_check_spelling.py")
        command = ["sudo", "-n", "-u", "postgres", "python3", "-B", str(checker), target, "-"]
        snapshot = (sealed / "source-snapshot.json.gz").read_bytes()
        changed_checks = json.loads(subprocess.check_output(command, input=snapshot))
        require(not json.loads(subprocess.check_output(command, input=snapshot)), "repeat-original-check-replay")
        receipt = out / "check-replay.json"
        if not receipt.is_file():
            save(receipt, {"sql_sha256": proof["sql_sha256"], "clauses": changed_checks})
        check_replay = json.loads(receipt.read_bytes())
        require(check_replay["sql_sha256"] == proof["sql_sha256"] and
                (not changed_checks or check_replay["clauses"] == changed_checks), "replay-witness-mismatch")
        from verify_converted_sql_schema import schema

        archive = subprocess.check_output(["pg_restore", "--schema-only", "--no-tablespaces", "--file=-",
                                           str(sealed / "source.dump")])
        live = pg("pg_dump", "--schema-only", "--no-tablespaces", source, readonly=True, stdout=subprocess.PIPE).stdout
        require(schema(archive) == schema(live), "source-schema-drift-before-view-replay")
        view_tool = Path(__file__).with_name("restore_original_view_spelling.py")
        view_args = ["sudo", "-n", "-u", "postgres", "python3", "-B", str(view_tool), source, target]
        changed_views = json.loads(subprocess.check_output(view_args))
        require(not json.loads(subprocess.check_output(view_args)), "repeat-original-view-replay")
        receipt = out / "view-replay.json"
        if not receipt.is_file():
            save(receipt, {"sql_sha256": proof["sql_sha256"], "definitions": changed_views})
        view_replay = json.loads(receipt.read_bytes())
        require(view_replay["sql_sha256"] == proof["sql_sha256"] and
                (not changed_views or view_replay["definitions"] == changed_views), "view-replay-witness-mismatch")
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
    extras = set()
    physical = sealed / "filestore-physical.json"
    if physical.exists():
        complete = json.loads(physical.read_text())
        require(complete["sql_sha256"] == proof["sql_sha256"] and complete["restored"] == target,
                "supplemental-filestore-identity-drift")
        extras = {name for name in complete["extras"] if not name.startswith("checklist/")}
    require({p.relative_to(dest).as_posix() for p in dest.glob("*/*") if p.is_file()} == catalog.keys() | extras
            and all((dest / n).stat().st_size == size and digest(dest / n, "sha1") == Path(n).name
                    for n, size in catalog.items()), "restored-filestore-drift")
    for directory in (out, sealed, sealed / "runtime", *(p for p in (sealed / "runtime").rglob("*") if p.is_dir())):
        os.chown(directory, 0, service.pw_gid)
        directory.chmod(0o750)
    for path in (data, *data.rglob("*")):
        require(not path.is_symlink(), "unexpected-restored-filestore-symlink")
        os.chown(path, service.pw_uid, service.pw_gid)
    origins = json.loads((sealed / "effective-providers.json").read_text())
    hidden_sources = [args.runtime, args.source_data, *args.addons, *(v[0] for v in origins.values())]
    orm = open_as_user(out, target, service, 1, hidden_sources)
    verify_same(frozen, full_snapshot(target))
    require(open_as_user(out, target, service, 2, hidden_sources) == orm, "second-cold-boot-differs")
    require(orm["active"] == len(modules) and check_modules(target) == modules, "restored-registry-drift")
    verify_same(frozen, full_snapshot(target))
    verify_same(source_at_start, full_snapshot(source))
    result = {**proof, "target": target, "tablespace": space, "full_post_boot_match": True,
              "source_unchanged": True, "source_unchanged_during_recovery": True,
              "source_sequence_advances_since_seal": advances, "checked_boots": 2, "role_probe": orm, "restored_filestore_objects": len(catalog)}
    if check_replay:
        result["exact_constraint_replay"] = check_replay
        result["exact_view_replay"] = view_replay
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
    parser.add_argument("--allow-forward-sequences-on-source", action="store_true",
                        help="Allow recorded sequence consumption on the live QA source since an existing seal")
    parsed = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore(parsed)
