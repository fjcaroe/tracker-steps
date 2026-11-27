"""Restore the independent 165-module Steps checkpoint using PostgreSQL 12 and Odoo in workstation RAM."""
import argparse
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

from verify_converted_backup import check, hash_file, read_json
from verify_steps_integrated_backup import FISCAL, H3_SHA, INVOICES, OFFICIAL, PORTAL as SUPPORT_PORTAL, RESTORED, module_archives, verify
from verify_steps_support_backup import PACKAGES, compressed, strong
from steps_barcode_runtime import BARCODE_SHA, verify as verify_barcode_runtime


MEM = Path("/dev/shm/steps-integrated-u46b")
SOCKET = str(MEM / "socket")
PORT = 55446
TOOLS = Path(__file__).resolve().parent
DB_USER, ODOO_USER = 61012, 61018
GIB = 1024**3


def call(user, command, **kwargs):
    run = [sys.executable, str(TOOLS / "run_focal_print_command.py"), "--user", user, "--", *map(str, command)]
    return subprocess.run(run, check=True, **kwargs)


def pg(command, *args, **kwargs):
    return call("postgres", [command, "-h", SOCKET, "-p", PORT, *args], **kwargs)


def query(db, sql):
    return pg("psql", "-XAtq", "-v", "ON_ERROR_STOP=1", "-d", db, "-c", sql, capture_output=True, text=True).stdout.strip()


def space(base, *, initial=False):
    meminfo = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        meminfo[key] = int(value.split()[0]) * 1024
    available = shutil.disk_usage("/dev/shm").free
    estimate = 1300 * 1024**2 if initial else 450 * 1024**2
    check(available >= estimate + GIB and meminfo["MemAvailable"] >= estimate + 2 * GIB and
          shutil.disk_usage(base).free >= 64 * 1024**2, "insufficient-workstation-RAM-or-receipt-space")
    return {"tmpfs_free": available, "memory_available": meminfo["MemAvailable"],
            "workstation_disk_free": shutil.disk_usage(base).free}


def checked_directory(path, mode, uid=0):
    check(path.resolve() == path and path.is_relative_to(MEM), "private-RAM-path-required")
    path.mkdir(exist_ok=True, parents=True, mode=mode)
    os.chown(path, uid, uid)
    path.chmod(mode)


def prepare(base, h3):
    check(os.getuid() == 0 and Path("/dev/shm").is_mount() and os.stat("/dev/shm").st_dev != os.stat("/").st_dev,
          "workstation-private-tmpfs-required")
    runtime = MEM / "runtime"
    space(base, initial=not runtime.exists())
    checked_directory(MEM, 0o711)
    check(hash_file(h3 / "checkpoint.json") == H3_SHA, "wrong-162-module-parent")
    members = read_json(base / "runtime-members.json")
    original = read_json(base / "backup.json")["runtime"]
    check(original["providers"] == 160 and hash_file(base / "runtime-members.json") == original["manifest_sha256"]
          and hash_file(base / "runtime.tar.gz") == original["archive_sha256"], "wrong-160-module-engine")
    if not runtime.exists():
        with tempfile.TemporaryDirectory(dir=MEM) as temp:
            stage = Path(temp) / "runtime"
            stage.mkdir(mode=0o755)
            remaining = set(members)
            with tarfile.open(base / "runtime.tar.gz", "r|gz") as archive:
                for m in archive:
                    path = stage / m.name
                    check(m.isfile() and path.resolve().is_relative_to(stage) and m.name in remaining,
                          "unrecognized-runtime-member")
                    remaining.remove(m.name)
                    size, sha, mode = members[m.name]
                    check([m.size, m.mode] == [size, mode] and mode in (0o644, 0o755), "runtime-file-metadata-drift")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(m) as src, path.open("xb") as out:
                        shutil.copyfileobj(src, out)
                    path.chmod(mode)
                    check(hash_file(path) == sha, "runtime-member-bytes-differ")
            check(not remaining, "runtime-file-missing")
            for root, _, _ in os.walk(stage):
                Path(root).chmod(0o755)
            stage.rename(runtime)
    check({p.relative_to(runtime).as_posix() for p in runtime.rglob("*") if p.is_file()} == members.keys() and
          all((runtime / n).resolve() == runtime / n and hash_file(runtime / n) == v[1] and
              (runtime / n).stat().st_uid == 0 and (runtime / n).stat().st_mode & 0o777 == v[2]
              for n, v in members.items()), "restored-runtime-differs")
    scripts = MEM / "tools"
    checked_directory(scripts, 0o755)
    todo = ["compare_sys_full_restore", "audit_steps_sales_schema", "probe_steps_support_thread",
            "probe_steps_fiscal_invoice_text", "steps_barcode_runtime"]
    seen = set()
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        source = TOOLS / (name + ".py")
        raw = source.read_bytes()
        target = scripts / source.name
        target.write_bytes(raw)
        target.chmod(0o644)
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node, ast.ImportFrom) and node.module and (TOOLS / (node.module + ".py")).is_file():
                todo.append(node.module)
    return len(members)


def cluster():
    checked_directory(MEM / "postgres", 0o700, DB_USER)
    checked_directory(MEM / "socket", 0o755, DB_USER)
    dbargs = ["-D", str(MEM / "postgres/cluster")]
    database = MEM / "postgres/cluster"
    if not database.exists():
        call("postgres", ["initdb", *dbargs, "--encoding=UTF8", "--lc-collate=C", "--lc-ctype=C.UTF-8",
                          "--auth-local=peer", "--auth-host=reject"], stdout=subprocess.DEVNULL)
        with (database / "postgresql.conf").open("a") as f:
            f.write(f"\nlisten_addresses=''\nport={PORT}\nunix_socket_directories='{SOCKET}'\nshared_buffers=32MB\n"
                    "min_wal_size=32MB\nmax_wal_size=96MB\njit=off\n")
    check((database / "PG_VERSION").read_text().strip() == "12", "private-PostgreSQL-12-required")
    try:
        call("postgres", ["pg_ctl", *dbargs, "status"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as error:
        if error.returncode != 3:
            raise
        call("postgres", ["pg_ctl", *dbargs, "-w", "-l", str(MEM / "postgres/server.log"), "start"],
             stdout=subprocess.DEVNULL)
    check(query("postgres", "SELECT current_setting('port')||'/'||current_setting('data_directory')")
          == str(PORT) + "/" + str(database), "wrong-private-server")


def snapshot(database=RESTORED):
    code = """
import json, sys, psycopg2
sys.path.insert(0, tools)
from compare_sys_full_restore import snapshot
from audit_steps_sales_schema import objects
with psycopg2.connect(dbname=db, host=sock, port=port, user="postgres") as conn:
    conn.set_session(readonly=True)
    with conn.cursor() as cr:
        def read_query(database, statement):
            assert database == db
            cr.execute(statement)
            return json.dumps(cr.fetchone()[0])
        ddl = objects(db, read_query)
print(json.dumps([snapshot(db, ('helpdesk_ticket','crm_lead'), socket_dir=sock, port=port), ddl]))
"""
    values = f"db={database!r}\nsock={SOCKET!r}\nport={PORT!r}\ntools={str(MEM / 'tools')!r}\n"
    return json.loads(call("postgres", ["python3.10", "-c", values + code], capture_output=True).stdout)


def schema_sha(database=RESTORED):
    dump = pg("pg_dump", "--schema-only", "--no-tablespaces", "-d", database, stdout=subprocess.PIPE).stdout
    normalized = b"\n".join(row for row in dump.splitlines() if not row.startswith((b"\\restrict ", b"\\unrestrict ")))
    return hashlib.sha256(normalized).hexdigest()


def boot(active, invoice_reference, chatter_reference, number, database=RESTORED, work=MEM, extra=None):
    proofdir = work / "proofs"
    conf = work / "odoo.conf"
    conf.write_text("[options]\nlist_db = False\n")
    conf.chmod(0o644)
    runtime = MEM / "runtime"
    addons = MEM / "addons"
    data = work / "data"
    roots = [addons, runtime / "addons", runtime / "odoo/addons"]
    if extra is not None:
        roots.insert(0, extra)
    cmd = ["env", "HOME=" + str(data), "TMPDIR=" + str(data / "tmp"),
           "PYTHONPATH=" + str(MEM / "barcode/python"), "python3.10", str(runtime / "odoo-bin"),
           "shell", "-c", str(conf), "-d", database, "--db-filter=^" + database + "$", "--db_host=" + SOCKET,
           "--db_port=" + str(PORT), "--data-dir=" + str(data), "--no-http", "--workers=0", "--max-cron-threads=0",
           "--addons-path=" + ",".join(map(str, roots)),
           "--without-demo=all", "--load=base,web", "--logfile=" + str(data / "odoo.log")]
    script = """
import json, logging, sys
from pathlib import Path
from odoo.modules.module import get_manifest, get_module_path
sys.path.insert(0, str(root / 'tools'))
from probe_steps_support_thread import internal, portal
from probe_steps_fiscal_invoice_text import run as invoices
assert env.cr.dbname == target and {row.split(':')[0].strip() for row in Path('/proc/net/dev').read_text().splitlines()[2:]}=={'lo'}
for name, values in active.items():
    path = root / ('addons' if name in overlay else 'runtime/odoo/addons' if name=='base' else 'runtime/addons') / name
    if name == 'step_payment_in_process':
        path = extra / name
    manifest = get_manifest(name)
    assert Path(get_module_path(name)).resolve(strict=True)==path and [manifest['version'],manifest['license']]==values
def as_actor(uid):
    user=env['res.users'].browse(uid)
    return env(user=uid,su=False,context={'allowed_company_ids':[user.company_id.id],'lang':user.lang or 'en_US','tracking_disable':True,'bin_size':False,'mail_notify_force_send':False})
tickets=as_actor(7)['helpdesk.ticket'].search([],order='id').ids
guest=as_actor(6)
invited=guest['helpdesk.ticket'].search([],order='id').ids
assert len(tickets)==243 and len(invited)==5 and guest.user.share
thread={'operators':[internal(as_actor(uid),tickets) for uid in (7,10)],
        'portal':portal(guest,as_actor(env.ref('base.public_user').id),invited,next(k for k in tickets if k not in invited))}
env.cr.rollback()
result=invoices(env)
assert result['database']==target
print('WORKFLOWS='+json.dumps([thread,result['documents']],sort_keys=True))
env.cr.rollback()
"""
    init = ("from pathlib import Path\nroot=Path(" + repr(str(MEM)) + ")\ntarget=" + repr(database) + "\nextra=" + ("Path(" + repr(str(extra)) + ")" if extra else "None") + "\nactive=" +
            repr(active) + "\noverlay=" + repr(sorted(PACKAGES.keys() | OFFICIAL.keys() | {FISCAL})) + "\n")
    log = proofdir / f"boot-{number}.log"
    with log.open("wb") as output:
        call("odoo", cmd, input=(init + script).encode(), stdout=output, stderr=output)
    (result,) = [json.loads(row[10:]) for row in log.read_bytes().splitlines() if row.startswith(b"WORKFLOWS=")]
    check(result == [chatter_reference, invoice_reference], "restored-invoice-or-ticket-content-differs")
    return strong(result)


def restore(base, h3, sealed, expected_sha, *, parent=None):
    files = prepare(base, h3)
    if parent is not None:
        from verify_steps_payment_release import verify as verify_payment
        target = "COMMUNITY_STEPS_CRM_RECOVERY_20261127U46C"
        work = MEM / "payment-recovery"
        def check_archives(destination=None):
            return verify_payment(base, h3, parent, sealed, expected_sha, destination)
        fiscal = parent
    else:
        target, work, fiscal = RESTORED, MEM, sealed
        def check_archives(destination=None):
            return verify(base, h3, sealed, expected_sha, destination)
    checked_directory(work, 0o711)
    status = check_archives()
    checked_directory(MEM / "barcode", 0o755)
    barcode = verify_barcode_runtime(fiscal / "steps-fiscal-barcode-runtime.tar.gz", BARCODE_SHA, MEM / "barcode")
    actual = json.loads(call("odoo", ["env", "PYTHONPATH=" + str(MEM / "barcode/python"), "python3.10",
                                     str(MEM / "tools/steps_barcode_runtime.py"), "probe"], capture_output=True).stdout)
    check(actual == barcode["reference"], "source-and-local-barcode-runtime-differ")
    proof = read_json(sealed / "checkpoint.json")
    active = read_json(sealed / "providers.json")
    check(len(active) == (166 if parent else 165) and "odoo" in proof["required_roles"], "wrong-integrated-installation")
    identity = {"source": status["source"], "restored": target, "checkpoint_sha256": expected_sha}
    marker = work / "identity.json"
    recorded = marker.exists()
    if marker.exists():
        check(read_json(marker) == identity, "another-database-already-owns-this-private-directory")
    else:
        check(parent is not None or not (MEM / "postgres/cluster").exists(), "unidentified-private-PostgreSQL-cluster")
    checked_directory(work / "proofs", 0o700)
    checked_directory(work / "data", 0o700, ODOO_USER)
    checked_directory(work / "data/tmp", 0o700, ODOO_USER)
    checked_directory(work / "data/filestore", 0o700, ODOO_USER)
    # Serialize the heavy SQL restore with the other products using the workstation's existing lock.
    with open("/dev/shm/steps-shared-qa-restore.lock", "a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before_capacity = space(base)
        cluster()
        if not recorded:
            check(not query("postgres", f"SELECT 1 FROM pg_database WHERE datname='{target}'"), "existing-unidentified-database")
            with marker.open("x") as receipt:
                json.dump(identity, receipt, sort_keys=True)
        for role in proof["required_roles"]:
            check(re.fullmatch(r"[a-z_][a-z0-9_]*", role), "unexpected-role-name")
            if not query("postgres", f"SELECT 1 FROM pg_roles WHERE rolname='{role}'"):
                pg("createuser", *(["--login"] if role == "odoo" else ["--no-login"]), role)
        if not query("postgres", f"SELECT 1 FROM pg_database WHERE datname='{target}'"):
            pg("createdb", "--owner=odoo", "--encoding=UTF8", "--template=template0", "--lc-collate=C",
               "--lc-ctype=C.UTF-8", target)
        if not query(target, "SELECT 1 FROM pg_class WHERE oid=to_regclass('public.ir_module_module')"):
            check(query(target, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") == "0", "nonempty-restore-target")
            with (sealed / "source.dump").open("rb") as inp, (work / "proofs/pg-restore.log").open("wb") as log:
                pg("pg_restore", "--no-tablespaces", "--single-transaction", "--exit-on-error", "-d", target,
                   stdin=inp, stdout=log, stderr=log)
    frozen = compressed(sealed, "snapshot.json.gz")
    ddl = compressed(sealed, "sql-objects.json.gz")
    check(snapshot(target) == [frozen, ddl], "restored-rows-sequences-or-SQL-objects-differ")
    check(schema_sha(target) == proof["schema_sha256"], "restored-complete-schema-differs")
    store = work / "data/filestore" / target
    physical = compressed(sealed, "filestore.json.gz")
    if not store.is_dir():
        with tempfile.TemporaryDirectory(dir=work / "data/filestore") as temp:
            staged = Path(temp) / "store"
            staged.mkdir()
            check_archives(staged)
            staged.rename(store)
    def tree():
        return {p.relative_to(store).as_posix(): [p.stat().st_size, hash_file(p)] for p in store.rglob("*") if p.is_file()}
    check(tree() == physical, "restored-physical-store-differs")
    for p in [store, *store.rglob("*")]:
        check(not p.is_symlink(), "unexpected-private-store-link")
        os.chown(p, ODOO_USER, ODOO_USER)
        p.chmod(0o700 if p.is_dir() else 0o600)
    overlay = MEM / "addons"
    if not overlay.is_dir():
        with tempfile.TemporaryDirectory(dir=MEM) as temp:
            stage = Path(temp) / "addons"
            stage.mkdir()
            module_archives(fiscal, active, read_json(fiscal / "checkpoint.json")["fiscal_package_sha256"], stage)
            for name in PACKAGES:
                if name == SUPPORT_PORTAL:
                    continue
                with tarfile.open(h3 / (name + ".tar")) as archive:
                    for m in archive:
                        path = stage / m.name
                        check(m.isfile() and path.resolve().is_relative_to(stage) and not path.exists(), "invalid-support-overlay")
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(archive.extractfile(m).read())
                        path.chmod(0o644)
            for root, _, _ in os.walk(stage):
                Path(root).chmod(0o755)
            stage.rename(overlay)
    expected_parent = {}
    archives = [fiscal / name for name in ("fiscal-release.tar", "official-fiscal.tar", "portal-release.tar")]
    archives += [h3 / (name + ".tar") for name in PACKAGES if name != SUPPORT_PORTAL]
    for path in archives:
        with tarfile.open(path) as bundle:
            for member in bundle:
                check(member.isfile() and member.name not in expected_parent, "overlapping-parent-module")
                expected_parent[member.name] = hashlib.sha256(bundle.extractfile(member).read()).hexdigest()
    parent_code = {p.relative_to(overlay).as_posix(): hash_file(p) for p in overlay.rglob("*") if p.is_file()}
    check(parent_code == expected_parent, "parent-overlay-differs-in-restored-product")
    extra = None
    if parent is not None:
        extra = work / "addons"
        checked_directory(extra, 0o755)
        with tarfile.open(sealed / "payment-release.tar") as archive:
            expected = set()
            for member in archive:
                dest = extra / member.name
                check(member.isfile() and dest.resolve().is_relative_to(extra) and dest not in expected, "unknown-payment-source")
                data = archive.extractfile(member).read()
                expected.add(dest)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    dest.write_bytes(data)
                    dest.chmod(0o644)
                check(dest.read_bytes() == data, "payment-addon-differs-from-release")
            check(expected == {p for p in extra.rglob("*") if p.is_file()}, "unexpected-payment-addon-code")
    with tarfile.open(sealed / "functional-evidence.tar") as archive:
        if parent is None:
            invoices = json.load(archive.extractfile(INVOICES))
            chatter = json.load(archive.extractfile("support-integrated.json"))
        else:
            chatter = json.load(archive.extractfile("support.json"))
            business = json.load(archive.extractfile("business.json"))
            options = [name for name in business["receipts"] if "invoice-text" in name and "native" not in name]
            matches = [json.load(archive.extractfile(name)) for name in options]
            invoices, = [r for r in matches if r.get("database") == status["source"] and len(r.get("documents", ())) == 42]
    check(invoices["database"] == chatter["db"] == status["source"] and len(invoices["documents"]) == 42,
          "wrong-integrated-workflow-expectations")
    signatures = []
    for number in (1, 2):
        signatures.append(boot(active, invoices["documents"], chatter["thread"], number, target, work, extra))
        check(snapshot(target) == [frozen, ddl] and tree() == physical, "post-boot-full-storage-drift")
    check(len(set(signatures)) == 1, "second-boot-differs")
    own_cluster = MEM / "postgres/cluster"
    check(query("postgres", "SELECT current_setting('port')||'/'||current_setting('data_directory')")
          == str(PORT) + "/" + str(own_cluster), "unrecognized-cluster-at-shutdown")
    call("postgres", ["pg_ctl", "-D", str(own_cluster), "-m", "fast", "-w", "stop"],
         stdout=subprocess.DEVNULL)
    result = {**status, **identity, "role_boots": 2, "runtime_files": files, "overlay_files": sum(p.is_file() for p in overlay.rglob("*")) + (len(expected) if extra is not None else 0),
              "original_invoice_reads_per_boot": len(invoices["documents"]), "original_threads_per_actor": 243,
              "operator_files_per_boot": 418, "portal_files_per_boot": 2, "workflows_sha256": signatures[0],
              "preflight": before_capacity, "postflight": space(base), "private_cluster_stopped": True,
              "barcode_runtime_sha256": BARCODE_SHA, "barcode_reference": actual}
    (work / "proofs/restored.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "restore"])
    parser.add_argument("base", type=Path)
    parser.add_argument("h3", type=Path)
    parser.add_argument("--sealed", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--parent-165", type=Path, help="Immutable parent checkpoint for the 166-module release")
    args = parser.parse_args()
    os.umask(0o022)
    if args.phase == "restore":
        if not (args.sealed and args.sha256):
            parser.error("--sealed and --sha256 are required")
        print(json.dumps(restore(args.base, args.h3, args.sealed, args.sha256, parent=args.parent_165), indent=2))
    else:
        print(json.dumps({"prepared_runtime_files": prepare(args.base, args.h3), "workstation": space(args.base)}))
