"""Restore the qualified SyS payroll snapshot and add the accepted library and portal in one private product."""
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

from capture_sys_combined_source import DOCUMENT_SHA, ORIGIN, ROOT, SOURCE, SPACE, TARGET, capacity
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog, restore_objects
from restore_converted_sys_cohort import check_modules, full_snapshot, save, verify_same
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import LOCK, require

SEALED = ROOT / "sealed"
DATA = ROOT / "data"
TOOLS = Path(__file__).resolve().parent
PORTAL = Path("/opt/steps-validation/community-document-portal-20261126U41P")
DOCUMENTS = ROOT / "documents"
PACKAGE = PORTAL / "folders-f2ea467610be/package.tar"
GOLDEN = "COMMUNITY_PORTAL_SYS_20261126U41PF"
SERVICE = pwd.getpwnam("odoo")
MEMBERSHIP_GUARD = " TRIGGER public res_groups_users_rel steps_sys_policy_row "


def command(shell=False, overlay=True, database=TARGET, data=DATA, sealed=SEALED, documents=DOCUMENTS):
    core = sealed / "runtime"
    roots = [core / "addons", core / "odoo/addons"]
    if overlay:
        roots.insert(0, documents / "addons")
    return ["unshare", "--net", "--", "sh", "-ec", 'ip link set dev lo up; exec "$@"', "odoo",
            "sudo", "-n", "-u", "odoo", "env", "PYTHONDONTWRITEBYTECODE=1", "/usr/bin/python3.10",
            str(core / "odoo-bin"), *(["shell"] if shell else []), "-c", "/etc/odoo18-sys.conf",
            "-d", database, "--db-filter=^" + database + "$", "--db_host=/var/run/postgresql", "--data-dir=" + str(data),
            "--addons-path=" + ",".join(map(str, roots)), "--no-http", "--workers=0", "--max-cron-threads=0",
            "--load=base,web", "--without-demo=all", "--stop-after-init", "--logfile=" + str(data / "odoo.log")]


def shell(code, marker="RESULT=", overlay=True, argv=None, error_root=ROOT):
    p = subprocess.run(argv if argv is not None else command(True, overlay), input=code.encode(), capture_output=True)
    if p.returncode:
        # Odoo errors may contain personal data. Keep the trace in the private copy only.
        (error_root / "shell-error.log").write_bytes(p.stderr)
        raise RuntimeError("private-shell-failed")
    return json.loads(next(s[len(marker):] for s in p.stdout.decode().splitlines() if s.startswith(marker)))


def fingerprint(database, table, order="id", where="true", omit=()):
    record = "to_jsonb(x)" + "".join(" - '" + key + "'" for key in omit)
    return json.loads(query(database, f"""SELECT json_build_array(count(*),encode(sha256(convert_to(
             coalesce(string_agg(encode(sha256(convert_to(({record})::text,'UTF8')),'hex'),''
             ORDER BY {order}),''),'UTF8')),'hex')) FROM {table} x WHERE {where}"""))


def trigger_catalog(database):
    return json.loads(query(database, """SELECT json_object_agg(c.relname||'.'||t.tgname,
        pg_get_triggerdef(t.oid)||'|'||t.tgenabled::text) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal"""))


def restore_database(root=ROOT, sealed=SEALED, source=SOURCE, target_db=TARGET, checkpoint=None, toc=None):
    receipt = json.loads((checkpoint or root / "source-checkpoint.json").read_bytes())
    archive = sealed / "source.dump"
    identity = {"source": source, "target": target_db, "tablespace": SPACE, "sql": digest(archive)}
    require(identity["sql"] == receipt["sql"], "source-sql-differs")
    marker = root / "admission-identity.json"
    exists = query("postgres", f"SELECT count(*) FROM pg_database WHERE datname='{target_db}'") == "1"
    if not marker.exists():
        require(not exists, "target-already-in-use")
        save(marker, identity)
    require(json.loads(marker.read_bytes()) == identity, "database-identity-drift")
    if not exists:
        enc, coll, typ = json.loads(query("postgres", f"""SELECT json_build_array(pg_encoding_to_char(encoding),
            datcollate,datctype) FROM pg_database WHERE datname='{source}' AND pg_get_userbyid(datdba)='odoo'"""))
        pg("createdb", "--owner=odoo", "--template=template0", "--tablespace=" + SPACE, "--encoding=" + enc,
           "--lc-collate=" + coll, "--lc-ctype=" + typ, target_db)
    require(query("postgres", f"""SELECT s.spcname FROM pg_database d JOIN pg_tablespace s ON s.oid=d.dattablespace
                                  WHERE d.datname='{target_db}' AND pg_get_userbyid(d.datdba)='odoo'""") == SPACE,
            "wrong-tablespace-or-owner")
    entries = subprocess.check_output(["pg_restore", "-l", str(archive)], text=True).splitlines()
    guard, = [row for row in entries if MEMBERSHIP_GUARD in row]
    toc = toc or Path("/opt/steps-validation/community-sys-combined-restore-toc-20261127U43C")
    toc.mkdir(exist_ok=True)
    gid = pwd.getpwnam("postgres").pw_gid
    os.chown(toc, 0, gid)
    toc.chmod(0o750)
    for name, lines in [("main", [row for row in entries if row != guard]), ("membership", [guard])]:
        target = toc / name
        target.write_text("\n".join(lines) + "\n")
        os.chown(target, 0, gid)
        target.chmod(0o640)
    def apply(section):
        with archive.open("rb") as handle, (root / ("restore-" + section + ".log")).open("ab") as log:
            pg("pg_restore", "--single-transaction", "--exit-on-error", "--no-tablespaces", "--use-list=" + str(toc / section),
               "--dbname=" + target_db, stdin=handle, stdout=log, stderr=log)
    if query(target_db, "SELECT to_regclass('public.ir_module_module') IS NULL") == "t":
        require(query(target_db, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") == "0", "partial-restore")
        apply("main")
    return apply


def restore_files(data=DATA, database=TARGET, sealed=SEALED, prepare_runtime=True):
    catalog = object_catalog(attachments(database, query)["references"])
    proof = json.loads((sealed / "filestore-physical.json").read_bytes())
    dest = data / "filestore" / database
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent) as folder:
            stage = Path(folder) / "files"
            stage.mkdir()
            restore_objects(sealed / "filestore.tar", stage, catalog)
            extra = sealed / "filestore-extra.tar"
            require(digest(extra) == proof["extra_archive_sha256"], "supplemental-filestore-drift")
            with tarfile.open(extra) as bundle:
                remaining = set(proof["extras"])
                for item in bundle:
                    require(item.isfile() and item.name in remaining, "unexpected-extra-filestore-file")
                    remaining.remove(item.name)
                    target = stage / item.name
                    require(target.resolve().is_relative_to(stage), "invalid-filestore-path")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(item) as src, target.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
                require(not remaining, "incomplete-supplement")
            items = inventory(stage, catalog)
            hashed = hashlib.sha256(json.dumps(items, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            require(hashed == proof["tree_sha256"], "source-physical-store-drift")
            stage.rename(dest)
    for path in [data, *data.rglob("*")]:
        require(not path.is_symlink(), "unexpected-data-symlink")
        os.chown(path, SERVICE.pw_uid, SERVICE.pw_gid)
    if not prepare_runtime:
        return
    core = sealed / "runtime"
    for folder in [sealed, core, *(p for p in core.rglob("*") if p.is_dir())]:
        os.chown(folder, 0, SERVICE.pw_gid)
        folder.chmod(0o750)


def prepare_portal_accounts(apply, root=ROOT, sealed=SEALED, source=SOURCE, database=TARGET, argv=None):
    expected = trigger_catalog(source)
    key = "res_groups_users_rel.steps_sys_policy_row"
    require(expected[key].endswith("|O"), "missing-original-guard")
    sealed_accounts = root / "actors-sealed.json"
    secret = root / "temporary-accounts.json"
    if sealed_accounts.exists():
        require(trigger_catalog(database) == expected and secret.stat().st_mode & 0o777 == 0o600,
                "changed-actor-seal")
        return
    cutoff = int(query(source, "SELECT max(id) FROM res_users"))
    if not secret.exists():
        require(trigger_catalog(database) == {k: v for k, v in expected.items() if k != key}, "wrong-preseal-state")
        frozen = json.loads(gzip.decompress((sealed / "source-snapshot.json.gz").read_bytes()))
        verify_same(frozen, full_snapshot(database))
        code = (TOOLS / "probe_document_portal_http.py").read_text() + (
            "\nresult=prepare_accounts(env)\nenv.cr.commit()\nprint('RESULT='+json.dumps(result))\n")
        prepared = shell(code, overlay=False, argv=argv, error_root=root)
        require(len(prepared) == 2 and min(a[0] for a in prepared) > cutoff, "unexpected-prepared-identities")
        save(secret, prepared)
        secret.chmod(0o600)
    if key not in trigger_catalog(database):
        apply("membership")
    require(trigger_catalog(database) == expected, "original-guard-catalog-drift")
    rows = {}
    for table, order, where in [("res_users", "id", f"id<={cutoff}"), ("res_groups_users_rel", "gid,uid", f"uid<={cutoff}"),
                                ("res_groups", "id", "true"), ("ir_rule", "id", "true"), ("ir_model_access", "id", "true"),
                                ("documents_document", "id", "true"), ("documents_access", "id", "true"),
                                ("ir_attachment", "id", "true"), ("mail_mail", "id", "true")]:
        rows[table] = fingerprint(source, table, order, where)
        require(rows[table] == fingerprint(database, table, order, where), "original-policy-drift:" + table)
    require(query(database, f"SELECT count(*) FROM res_users WHERE id>{cutoff}") == "2", "unexpected-fixture-accounts")
    save(sealed_accounts, {"original": rows, "new_portal_accounts": 2, "guards": len(expected), "original_uid_cutoff": cutoff})


def install_documents():
    require(digest(PACKAGE) == DOCUMENT_SHA, "document-package-drift")
    expected = set()
    roots = {"step_document_library", "step_document_library_portal"}
    with tarfile.open(PACKAGE) as bundle:
        for item in bundle:
            name = Path(item.name)
            if item.isdir():
                require(name.parts and name.parts[0] == 'addons' and '..' not in name.parts and
                        (len(name.parts) == 1 or name.parts[1] in roots), 'unexpected-document-directory')
                continue
            require(item.isfile() and len(name.parts) >= 3 and name.parts[0] == "addons" and
                    name.parts[1] in roots and ".." not in name.parts and name not in expected, "unexpected-doc-module")
            expected.add(name)
            dest = DOCUMENTS / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(item) as payload:
                raw = payload.read()
            if not dest.exists():
                with dest.open("xb") as out:
                    out.write(raw)
            require(dest.read_bytes() == raw, "changed-document-package")
            dest.chmod(0o644)
    for path in [DOCUMENTS, *(p for p in DOCUMENTS.rglob("*") if p.is_dir())]:
        os.chown(path, 0, SERVICE.pw_gid)
        path.chmod(0o750)
    require(expected == {p.relative_to(DOCUMENTS) for p in DOCUMENTS.rglob("*") if p.is_file()},
            "undocumented-document-package-member")
    modules = check_modules(TARGET)
    source_modules = check_modules(SOURCE)
    if modules.keys() == source_modules.keys():
        with (ROOT / "document-install.log").open("ab") as log:
            subprocess.run(command() + ["-i", "step_document_library,step_document_library_portal"],
                           stdout=log, stderr=log, check=True)
    result = check_modules(TARGET)
    expected_modules = {**source_modules, "step_document_library": ["18.0.1.0.5", "AGPL-3"],
                        "step_document_library_portal": ["18.0.1.0.3", "LGPL-3"]}
    require(result == expected_modules, "combined-registry-drift")


def adopt():
    # The accepted documents copy holds only digests and the native non-secret token affixes.
    historical = json.loads(query(GOLDEN, """SELECT json_build_object('original_identity', encode(sha256(convert_to(
        string_agg(json_build_array(id,document_token,url)::text,chr(10) ORDER BY id),'UTF8')),'hex'),
        'hashes',json_object_agg(id,step_original_url_hash),'portal',json_build_object('identity',encode(sha256(convert_to(
        string_agg(json_build_array(id,document_token)::text,chr(10) ORDER BY id),'UTF8')),'hex'),
        'digests',json_object_agg(id,step_portal_reference_hash),'affixes',
        json_object_agg(id,json_build_array(step_portal_reference_prefix,step_portal_reference_suffix))))
        FROM documents_document"""))
    portal = historical.pop("portal")
    require(len(portal["digests"]) == len(historical["hashes"]) == 1430, "qualified-document-source-drift")
    code = (TOOLS / "adopt_document_library_links.py").read_text() + "\n" + (TOOLS / "adopt_document_portal_tokens.py").read_text()
    code += "\nimport json\ndef apply_catalogs():\n    return [adopt_links(env," + repr(historical) + "),adopt_portal_references(env," + repr(portal) + ")]\n"
    code += "first=apply_catalogs()\nsecond=apply_catalogs()\nassert second==[0,0]\nenv.cr.commit()\nprint('RESULT='+json.dumps([first,second]))\n"
    writes = shell(code)
    require(writes[0] in ([0, 0], [1430, 1430]) and writes[1] == [0, 0], "incomplete-catalog-adoption")
    receipt = ROOT / "combined-admission.json"
    if not receipt.exists():
        save(receipt, {"source": SOURCE, "target": TARGET, "historical_documents": 1430,
                       "link_writes": writes, "package_sha256": DOCUMENT_SHA, "module_count": len(check_modules(TARGET))})


if __name__ == "__main__":
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        capacity()
        restore_membership = restore_database()
        restore_files()
        prepare_portal_accounts(restore_membership)
        install_documents()
        adopt()
