"""Admit two exact support providers into a new, guarded copy of the recovered Steps sales and document product."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tarfile
import tempfile

from admit_steps_sales_documents import odoo
from audit_steps_sales_schema import objects
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog, restore_objects
from load_steps_sales_extension import guarded_command
from restore_converted_sys_cohort import check_modules, full_snapshot, save, verify_same
from restore_native_product_backup import pg, query
from restore_steps_sales_backup import BASE, SPACE
from restore_sys_previred_pair import GIB, LOCK, require


SOURCE = "COMMUNITY_STEPS_CRM_RECOVERY_20261127U44R"
TARGET = "COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3"
WORK = BASE / "steps-sales-support-20261127U44H3"
RECOVERY = BASE / ("recovery-" + SOURCE.lower())
SEALED = RECOVERY / "sealed"
SUPPORT = "step_helpdesk_tickets"
PORTAL = "step_helpdesk_tickets_portal"
SQL_SHA = "602069d8a5a8a43ff2af901f994794189a50c20857c40490d14c4bc7aa9c054b"
SUPPORT_SHA = "00adc8a137ad753c097383a928c25a5c4bb4e5098c189c195e3fbb2805f57207"
GROUP = pwd.getpwnam("odoo").pw_gid


def runtime_files():
    files = json.loads((SEALED / "runtime-members.json").read_bytes())
    target = WORK / "runtime"
    if not target.exists():
        with tempfile.TemporaryDirectory(dir=WORK) as tmp:
            stage = Path(tmp) / "runtime"
            stage.mkdir()
            for name, (size, sha, mode) in files.items():
                source = SEALED / "runtime" / name
                dest = stage / name
                require(source.resolve() == source and dest.resolve().is_relative_to(stage)
                        and source.stat().st_size == size and digest(source) == sha and source.stat().st_mode & 0o777 == mode,
                        "recovered-runtime-member-differs")
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.link(source, dest)
            for folder in [stage, *(p for p in stage.rglob("*") if p.is_dir())]:
                os.chown(folder, 0, GROUP)
                folder.chmod(0o750)
            stage.rename(target)
    actual = {p.relative_to(target).as_posix(): p for p in target.rglob("*") if p.is_file()}
    require(actual.keys() == files.keys() and all(
        actual[n].samefile(SEALED / "runtime" / n) and digest(actual[n]) == v[1] for n, v in files.items()),
        "wrong-steps-runtime")
    return target


def release(name, source, expected):
    require(digest(source) == expected, "support-package-sha256")
    dest = WORK / "releases" / expected
    dest.mkdir(parents=True, exist_ok=True)
    members = {}
    with tarfile.open(source) as archive:
        for m in archive:
            key = Path(m.name)
            require(m.isfile() and len(key.parts) >= 2 and key.parts[0] == name and ".." not in key.parts
                    and m.name not in members, "wrong-addon-package-member")
            f = dest / key
            require(f.resolve().is_relative_to(dest), "unexpected-package-link")
            payload = archive.extractfile(m).read()
            f.parent.mkdir(parents=True, exist_ok=True)
            if not f.exists():
                f.write_bytes(payload)
                f.chmod(0o644)
            require(not f.is_symlink() and f.read_bytes() == payload, "changed-support-provider")
            members[m.name] = hashlib.sha256(payload).hexdigest()
    require(set(members) == {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
            and name + "/__manifest__.py" in members and (name != SUPPORT or len(members) == 6),
            "unexpected-steps-support-provider-files")
    for folder in [dest.parent, dest, *(p for p in dest.rglob("*") if p.is_dir())]:
        os.chown(folder, 0, GROUP)
        folder.chmod(0o750)
    return dest


def storage(frozen, sql_sha):
    identity = {"copy": TARGET, "source": SOURCE, "sql": sql_sha, "support": SUPPORT_SHA, "tablespace": SPACE}
    marker = WORK / "identity.json"
    exists_sql = f"SELECT count(*) FROM pg_database WHERE datname='{TARGET}'"
    exists = query("postgres", exists_sql) == "1"
    if not marker.exists():
        require(not exists, "unused-steps-support-copy-required")
        save(marker, identity)
    require(json.loads(marker.read_bytes()) == identity, "unrelated-steps-support-copy")
    if not exists:
        pg("createdb", "--template=template0", "--owner=odoo", "--tablespace=" + SPACE,
           "--encoding=UTF8", "--lc-collate=C", "--lc-ctype=C.UTF-8", TARGET)
    placement = query("postgres", f"""SELECT pg_get_userbyid(datdba)||'/'||spcname FROM pg_database d
                      JOIN pg_tablespace s ON s.oid=d.dattablespace WHERE d.datname='{TARGET}'""")
    require(placement == "odoo/" + SPACE, "unexpected-steps-database-owner-or-volume")
    if query(TARGET, "SELECT to_regclass('public.ir_module_module') IS NULL") == "t":
        require(query(TARGET, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") == "0", "target-is-not-empty")
        with (SEALED / "source.dump").open("rb") as stream, (WORK / "pg-restore.log").open("ab") as log:
            pg("pg_restore", "--no-tablespaces", "--single-transaction", "--exit-on-error", "-d", TARGET,
               stdin=stream, stdout=log, stderr=log)
    expected = json.loads((SEALED / "filestore-physical.json").read_bytes())
    dest = WORK / "data/filestore" / TARGET
    catalog = object_catalog(attachments(TARGET, query)["references"])
    if not dest.is_dir():
        verify_same(frozen, full_snapshot(TARGET))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent) as temp:
            stage = Path(temp) / "files"
            stage.mkdir()
            restore_objects(SEALED / "filestore.tar", stage, catalog)
            remaining = set(expected["extras"])
            extra = SEALED / "filestore-extra.tar"
            require(digest(extra) == expected["extra_archive_sha256"], "wrong-steps-extra-archive")
            with tarfile.open(extra) as archive:
                for m in archive:
                    require(m.isfile() and m.name in remaining, "unknown-steps-extra-file")
                    remaining.remove(m.name)
                    file = stage / m.name
                    require(file.resolve().is_relative_to(stage), "unsafe-extra-path")
                    file.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(m) as src, file.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
            require(not remaining, "missing-extra-steps-files")
            stage.rename(dest)
    files = inventory(dest, catalog)
    tree = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(tree == expected["tree_sha256"] and len(files) == expected["all_files"], "restored-steps-filestore-drift")
    user = pwd.getpwnam("odoo")
    for p in [WORK / "data", *(WORK / "data").rglob("*")]:
        require(not p.is_symlink(), "unexpected-steps-file-link")
        os.chown(p, user.pw_uid, user.pw_gid)


def compare_original(frozen, schema_objects):
    after = full_snapshot(TARGET)
    sections = ("columns", "constraints", "relation_owner_and_acl", "sequence_definitions")
    for key in sections:
        require(all(after[key].get(k) == v for k, v in frozen[key].items()), "original-steps-schema-drift:" + key)
    now = objects(TARGET)
    require(all(now.get(k) == v for k, v in schema_objects.items()), "original-steps-views-indexes-or-owners-changed")
    prefixes = ("helpdesk_", "mail_", "crm_", "sale_", "account_", "documents_")
    names = [n for n in frozen["public_tables"] if n.startswith(prefixes) or n in
             ("res_company", "res_partner", "res_users", "ir_attachment", "ir_rule", "ir_model_access", "res_groups_users_rel")]
    require(all(after["public_tables"].get(n) == frozen["public_tables"][n] for n in names), "stored-steps-business-or-policy-drift")
    return {"unchanged_business_tables": len(names), "unchanged_original_sql_objects": len(schema_objects),
            "retained_schema": {k: len(frozen[k]) for k in sections}}


def admit(sql_sha, receipt_sha, portal_sha, repeat):
    require(Path(__file__).resolve().parent == WORK / "code" and WORK.resolve(strict=True) == WORK, "private-steps-work-required")
    require(sql_sha == SQL_SHA and digest(RECOVERY / "restore-proof.json") == receipt_sha and digest(SEALED / "source.dump") == sql_sha and
            json.loads((RECOVERY / "restore-proof.json").read_bytes())["target"] == SOURCE, "accepted-R-recovery-required")
    volume = Path(query("postgres", f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{SPACE}'"))
    db_size = int(query("postgres", f"SELECT pg_database_size('{SOURCE}')"))
    require(volume.resolve().is_relative_to(BASE / "community-payroll-storage-20261028") and
            shutil.disk_usage(volume).free > 5 * GIB + 2 * db_size and shutil.disk_usage(query("postgres", "SHOW data_directory")).free > 5 * GIB,
            "reserve-private-steps-storage")
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname IN ('{SOURCE}','{TARGET}')") == "0",
            "another-steps-recovery-session")
    frozen = json.loads(gzip.decompress((SEALED / "source-snapshot.json.gz").read_bytes()))
    verify_same(frozen, full_snapshot(SOURCE))
    core = runtime_files()
    support = release(SUPPORT, BASE / "steps-sales-support-20261127U44H2/support.tar", SUPPORT_SHA)
    portal = release(PORTAL, WORK / (portal_sha + ".tar"), portal_sha)
    storage(frozen, sql_sha)
    command = odoo(shell=True, work=WORK, target=TARGET)
    command[command.index(next(s for s in command if s.endswith("/odoo-bin")))] = str(core / "odoo-bin")
    command[command.index(next(s for s in command if s.startswith("--addons-path=")))] = "--addons-path=" + ",".join(
        map(str, (portal, support, core / "addons", core / "odoo/addons")))
    save(WORK / "private-args.json", command)
    schemas = objects(SOURCE)
    expected = check_modules(SOURCE)
    require(len(expected) == 160 and SUPPORT not in expected and PORTAL not in expected, "unexpected-combined-steps-source")
    receipt = []
    for name, version in ((SUPPORT, "18.0.1.0.1"), (PORTAL, "18.0.1.0.1")):
        installed = check_modules(TARGET)
        if name not in installed:
            switch = "-i"
        elif name == PORTAL and repeat:
            require(installed[PORTAL] in (["18.0.1.0.0", "LGPL-3"], [version, "LGPL-3"]),
                    "unsupported-or-newer-portal-version")
            switch = "-u"
        else:
            require(installed[name] == [version, "LGPL-3"], "different-installed-provider")
            continue
        compare_original(frozen, schemas)
        direct = [s for s in command if s != "shell"] + [switch, name]
        with (WORK / (name + "-" + switch[1] + ".log")).open("ab") as log:
            subprocess.run(guarded_command(direct, WORK, frozen), stdout=log, stderr=log, check=True)
        require(check_modules(TARGET)[name] == [version, "LGPL-3"], "new-provider-version-drift")
        receipt.append({"module": name, "operation": switch, "from": installed.get(name), "to": version,
                        **compare_original(frozen, schemas)})
    installed = check_modules(TARGET)
    require(installed == {**expected, SUPPORT: ["18.0.1.0.1", "LGPL-3"], PORTAL: ["18.0.1.0.1", "LGPL-3"]},
            "unexpected-steps-registry")
    result = {"database": TARGET, "source": SOURCE, "sql": sql_sha, "support": SUPPORT_SHA, "portal": portal_sha,
              "installed": len(installed), "loads": receipt, "final": compare_original(frozen, schemas)}
    from_version = next((row["from"][0] for row in receipt if row["module"] == PORTAL and row["from"]), None)
    suffix = "-from-" + from_version if from_version else ""
    save(WORK / ("admission-" + portal_sha[:12] + suffix + ".json"), result)
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql-sha", required=True)
    parser.add_argument("--recovery-sha", required=True)
    parser.add_argument("--portal-sha", required=True)
    parser.add_argument("--repeat", action="store_true")
    params = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        admit(params.sql_sha, params.recovery_sha, params.portal_sha, params.repeat)
