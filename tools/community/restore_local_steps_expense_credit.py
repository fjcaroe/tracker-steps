"""Recover the 168-module Steps checkpoint into a private PostgreSQL 12 cluster on the workstation's temporary RAM volume."""
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
from tempfile import TemporaryDirectory

from restore_local_steps_integrated import DB_USER, ODOO_USER, snapshot
from seal_converted_runtime import extract_runtime
from steps_barcode_runtime import BARCODE_SHA, verify as verify_barcode
from verify_converted_backup import check, hash_file, read_json
from verify_steps_expense_credit_backup import MODULES, verify
from verify_steps_support_backup import base_parts, compressed, strong

HOST=Path("/tmp/steps-expense-recovery-u50")
GUEST=Path("/dev/shm/steps-expense-recovery-u50")
CACHE=Path("/dev/shm/steps-integrated-u46b/runtime")
TOOLS=Path(__file__).resolve().parent
DB="COMMUNITY_STEPS_EXPENSE_RECOVERY_20261127U50R"
PORT=55449


def call(user, command, **kwargs):
    argv=[sys.executable,str(TOOLS/"run_focal_print_command.py"),"--steps-expense-recovery","--user",user,"--",*map(str,command)]
    return subprocess.run(argv,check=True,**kwargs)


def pg(program,*args,**kwargs):
    return call("postgres",[program,"-h",GUEST/"socket","-p",PORT,*args],**kwargs)


def sql(db,statement):
    return pg("psql","-XAtq","-v","ON_ERROR_STOP=1","-d",db,"-c",statement,capture_output=True,text=True).stdout.strip()


def prepare_code(args):
    base=base_parts(args.base)
    members=read_json(base/"runtime-members.json")
    record=read_json(base/"backup.json")["runtime"]
    check(hash_file(base/"runtime-members.json")==record["manifest_sha256"] and
          hash_file(base/"runtime.tar.gz")==record["archive_sha256"],"wrong-168-runtime-parent")
    host_engine=CACHE if CACHE.is_dir() else HOST/"runtime"
    guest_engine=CACHE if host_engine==CACHE else GUEST/"runtime"
    if not host_engine.exists():
        with TemporaryDirectory(dir=HOST) as temp:
            fresh=Path(temp)/"engine"
            extract_runtime(base/"runtime.tar.gz",fresh,members)
            for path,_,_ in os.walk(fresh):
                Path(path).chmod(0o755)
            fresh.rename(host_engine)
    check({p.relative_to(host_engine).as_posix() for p in host_engine.rglob("*") if p.is_file()}==members.keys()
          and all((host_engine/n).resolve(strict=True)==host_engine/n and hash_file(host_engine/n)==values[1]
                  and (host_engine/n).stat().st_mode&0o777==values[2] for n,values in members.items()),"168-base-runtime-drift")
    overlay=HOST/"addons"
    overlay.mkdir(exist_ok=True)
    sources=[args.h3/"step_helpdesk_tickets.tar",*(args.fiscal/n for n in ("fiscal-release.tar","official-fiscal.tar","portal-release.tar")),
             args.payments/"payment-release.tar",*(args.folder/(n+".tar") for n in MODULES)]
    files={}
    for archive in sources:
        with tarfile.open(archive) as tar:
            for member in tar:
                name=member.name
                path=overlay/name
                check(member.isfile() and path.resolve().is_relative_to(overlay) and name not in files,"overlapping-168-addon")
                raw=tar.extractfile(member).read()
                files[name]=hashlib.sha256(raw).hexdigest()
                path.parent.mkdir(exist_ok=True,parents=True)
                if not path.exists():
                    path.write_bytes(raw)
                    path.chmod(0o644)
                check(path.resolve(strict=True)==path and hash_file(path)==files[name],"incorrect-168-addon-bytes")
    check(files.keys()=={p.relative_to(overlay).as_posix() for p in overlay.rglob("*") if p.is_file()},"unexpected-168-addon")
    for path,_,_ in os.walk(overlay):
        Path(path).chmod(0o755)
    private=HOST/"tools"
    private.mkdir(exist_ok=True,mode=0o755)
    needed=["compare_sys_full_restore","audit_steps_sales_schema","probe_steps_support_thread","probe_steps_fiscal_invoice_text","steps_barcode_runtime"]
    copied=set()
    while needed:
        module=needed.pop()
        if module in copied:
            continue
        copied.add(module)
        file=TOOLS/(module+".py")
        raw=file.read_bytes()
        (private/file.name).write_bytes(raw)
        (private/file.name).chmod(0o644)
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node,ast.ImportFrom) and node.module and (TOOLS/(node.module+".py")).is_file():
                needed.append(node.module)
    barcode=HOST/"barcode"
    barcode.mkdir(exist_ok=True,mode=0o755)
    original=verify_barcode(args.fiscal/"steps-fiscal-barcode-runtime.tar.gz",BARCODE_SHA,barcode)
    observed=json.loads(call("odoo",["env","PYTHONPATH="+str(GUEST/"barcode/python"),"python3.10",GUEST/"tools/steps_barcode_runtime.py","probe"],
                             capture_output=True).stdout)
    check(observed==original["reference"],"different-168-barcode-environment")
    return guest_engine,len(members),len(files)


def start():
    server=GUEST/"postgres/cluster"
    if not (HOST/"postgres/cluster/PG_VERSION").is_file():
        call("postgres",["initdb","-D",server,"--encoding=UTF8","--lc-collate=C","--lc-ctype=C.UTF-8",
                         "--auth-local=peer","--auth-host=reject"],stdout=subprocess.DEVNULL)
        with (HOST/"postgres/cluster/postgresql.conf").open("a") as handle:
            handle.write(f"\nlisten_addresses=''\nport={PORT}\nunix_socket_directories='{GUEST}/socket'\nshared_buffers=32MB\n"
                         "min_wal_size=32MB\nmax_wal_size=96MB\njit=off\n")
    check((HOST/"postgres/cluster/PG_VERSION").read_text().strip()=="12","private-168-PostgreSQL-12-required")
    try:
        call("postgres",["pg_ctl","-D",server,"status"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as failure:
        if failure.returncode != 3:
            raise
        call("postgres",["pg_ctl","-D",server,"-w","start","-l",GUEST/"postgres/server.log"],stdout=subprocess.DEVNULL)
    check(sql("postgres","SELECT current_setting('port')||'/'||current_setting('data_directory')")
          ==str(PORT)+"/"+str(server),"wrong-168-recovery-server")


def reopen_verified_cluster():
    receipt=read_json(HOST/"restored.json")
    identity=read_json(HOST/"identity.json")
    check(receipt["role_boots"]==2 and receipt["recovery"]==identity["recovery"]==DB
          and identity["checkpoint"]==receipt["checkpoint_sha256"] and (HOST/"postgres/cluster/PG_VERSION").is_file(),
          "use-the-accepted-168-local-copy")
    start()
    return {"database":DB,"port":PORT,"socket":str(GUEST/"socket"),"host_files":str(HOST),"guest_files":str(GUEST)}


def stop_verified_cluster():
    server=GUEST/"postgres/cluster"
    check(sql("postgres","SELECT current_setting('data_directory')")==str(server)
          and sql("postgres","SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid()")=="0",
          "168-private-cluster-still-in-use")
    call("postgres",["pg_ctl","-D",server,"-m","fast","-w","stop"],stdout=subprocess.DEVNULL)


def odoo_profile(engine):
    cfg=HOST/"odoo.conf"
    cfg.write_text("[options]\nlist_db=False\n")
    cfg.chmod(0o644)
    cmd=["env","PYTHONPATH="+str(GUEST/"barcode/python"),"TMPDIR="+str(GUEST/"data/tmp"),"HOME="+str(GUEST/"data"),
         "python3.10",engine/"odoo-bin","shell","-c",GUEST/"odoo.conf","-d",DB,"--db-filter=^"+DB+"$",
         "--db_host="+str(GUEST/"socket"),"--db_port="+str(PORT),"--no-http","--max-cron-threads=0","--workers=0",
         "--without-demo=all","--load=base,web","--data-dir="+str(GUEST/"data"),
         "--addons-path="+",".join(map(str,(GUEST/"addons",engine/"addons",engine/"odoo/addons"))),"--logfile="+str(GUEST/"data/odoo.log")]
    profile = HOST/"recovery-profile.json"
    if profile.exists():
        check(read_json(profile)==list(map(str,cmd)),"unexpected-168-private-launch-arguments")
    else:
        profile.write_text(json.dumps(list(map(str,cmd)),indent=2))
        profile.chmod(0o600)
    return cmd


def boot(engine, active, support, invoices):
    cmd=odoo_profile(engine)
    script="""
import json,sys
from pathlib import Path
from lxml import etree
from odoo.modules.module import get_manifest,get_module_path
sys.path.insert(0,str(root/'tools'))
from probe_steps_support_thread import internal,portal
from probe_steps_fiscal_invoice_text import run as fiscal_reads
assert env.cr.dbname==db and {l.split(':')[0].strip() for l in Path('/proc/net/dev').read_text().splitlines()[2:]}=={'lo'}
env.cr.rollback()
env.cr.execute('SET TRANSACTION READ ONLY')
for name,version in active.items():
    manifest=get_manifest(name)
    selected=Path(get_module_path(name)).resolve(strict=True)
    override=root/'addons'/name
    expected=override if override.is_dir() else engine/('odoo/addons' if name=='base' else 'addons')/name
    assert selected==expected and [manifest['version'],manifest['license']]==version
def operator(uid):
    user=env['res.users'].browse(uid)
    return env(user=uid,su=False,context={'allowed_company_ids':[user.company_id.id],'lang':user.lang,'tracking_disable':True,'bin_size':False,'mail_notify_force_send':False})
users=[operator(i) for i in (7,10)]
tickets=users[0]['helpdesk.ticket'].search([],order='id').ids
guest=operator(6)
visible=guest['helpdesk.ticket'].search([],order='id').ids
assert len(visible)==5 and len(tickets)==243
chatter={'operators':[internal(actor,tickets) for actor in users],
         'portal':portal(guest,operator(env.ref('base.public_user').id),visible,next(i for i in tickets if i not in visible))}
finance=users[1]
wizard=etree.fromstring(finance['account.move.reversal'].get_view(view_type='form')['arch'])
names={node.get('name') for node in wizard.xpath('//field')}
assert {'l10n_cl_original_text','l10n_cl_corrected_text','l10n_cl_is_text_correction','l10n_cl_edi_reference_doc_code'}<=names
assert wizard.xpath('//button[@name="refund_moves"]')
for model in ('hr.expense','hr.expense.sheet'):
    records=finance[model].search([],order='id')
    assert len(records)==3 and len(records.web_read({'name':{},'state':{}}))==3
    assert finance[model].get_view(view_type='form')['arch']
env.cr.rollback()
documents=fiscal_reads(env)
assert documents['database']==db
print('RESTORED='+json.dumps([chatter,documents['documents']],sort_keys=True))
env.cr.rollback()
"""
    init="from pathlib import Path\nroot=Path("+repr(str(GUEST))+")\nengine=Path("+repr(str(engine))+")\ndb="+repr(DB)+"\nactive="+repr(active)+"\n"
    result=call("odoo",cmd,input=(init+script).encode(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout
    matches=[json.loads(line[9:]) for line in result.splitlines() if line.startswith(b"RESTORED=")]
    if not matches:
        (HOST/"odoo-recovery-last.log").write_bytes(result)
    check(matches==[[support,invoices]],"168-cold-workflows-differ")
    return strong(matches[0])


def recover(args):
    check(os.getuid()==0 and subprocess.check_output(["findmnt","-n","-o","FSTYPE","--target","/tmp"],text=True).strip()=="tmpfs",
          "Steps-168-recovery-requires-RAM")
    HOST.mkdir(mode=0o711,exist_ok=True)
    check(HOST.resolve(strict=True)==HOST and HOST.stat().st_uid==0,"unexpected-168-RAM-directory")
    HOST.chmod(0o711)
    proof=read_json(args.folder/"checkpoint.json")
    identity={"source":proof["source"],"recovery":DB,"checkpoint":args.sha256}
    ident=HOST/"identity.json"
    if not ident.exists():
        check(not list(HOST.iterdir()),"unrecognized-168-recovery-files")
        ident.write_text(json.dumps(identity,sort_keys=True))
    check(read_json(ident)==identity,"168-private-recovery-identity-mismatch")
    mem=int(next(l.split()[1] for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemAvailable:")))*1024
    check(shutil.disk_usage(HOST).free>=2*1024**3 and mem>=3*1024**3,"168-local-memory-reserve")
    summary=verify(args.base,args.h3,args.fiscal,args.payments,args.folder,args.sha256)
    for sub,user,mode in (("socket",DB_USER,0o755),("postgres",DB_USER,0o700),("data",ODOO_USER,0o700),
                           ("data/tmp",ODOO_USER,0o700),("data/filestore",ODOO_USER,0o700)):
        path=HOST/sub
        path.mkdir(mode=mode,exist_ok=True)
        os.chown(path,user,user)
        path.chmod(mode)
    engine, runtime_files, addon_files=prepare_code(args)
    fs=HOST/"data/filestore"/DB
    if not fs.exists():
        with TemporaryDirectory(dir=fs.parent) as temp:
            target=Path(temp)/"files"
            target.mkdir()
            verify(args.base,args.h3,args.fiscal,args.payments,args.folder,args.sha256,target)
            target.rename(fs)
    physical=compressed(args.folder,"filestore.json.gz")
    def tree():
        return {p.relative_to(fs).as_posix():[p.stat().st_size,hash_file(p)] for p in fs.rglob("*") if p.is_file()}
    check(tree()==physical,"168-recovered-file-bytes-differ")
    for path in (fs,*fs.rglob("*")):
        check(not path.is_symlink(),"unexpected-168-file-link")
        os.chown(path,ODOO_USER,ODOO_USER)
        path.chmod(0o700 if path.is_dir() else 0o600)
    with tarfile.open(args.folder/"functional-evidence.tar") as arc:
        support=json.load(arc.extractfile("support-integrated.json"))["thread"]
        invoices=json.load(arc.extractfile("U50FullFiscal-steps-invoice-text-fiscal.json"))["documents"]
    check(len(invoices)==42,"wrong-original-invoice-evidence")
    expected=[compressed(args.folder,"snapshot.json.gz"),compressed(args.folder,"sql-objects.json.gz")]
    active=read_json(args.folder/"providers.json")
    def audit():
        return snapshot(DB,socket_dir=GUEST/"socket",port_number=PORT,tools_root=GUEST/"tools",execute=call)
    start()
    try:
        for role in proof["required_roles"]:
            check(re.fullmatch(r"[a-z_][a-z0-9_]*",role),"wrong-168-role")
            if not sql("postgres",f"SELECT 1 FROM pg_roles WHERE rolname='{role}'"):
                pg("createuser","--login" if role=="odoo" else "--no-login",role)
        if not sql("postgres",f"SELECT 1 FROM pg_database WHERE datname='{DB}'"):
            pg("createdb","--owner=odoo","--template=template0","--encoding=UTF8","--lc-collate=C","--lc-ctype=C.UTF-8",DB)
        if sql(DB,"SELECT count(*) FROM pg_tables WHERE schemaname='public'")=="0":
            with (args.folder/"source.dump").open("rb") as source,(HOST/"pg-restore.log").open("wb") as log:
                pg("pg_restore","--exit-on-error","--single-transaction","--no-tablespaces","-d",DB,stdin=source,stdout=log,stderr=log)
        check(audit()==expected,"168-restored-SQL-rows-or-sequences-differ")
        ddl=pg("pg_dump","--schema-only","--no-tablespaces","-d",DB,stdout=subprocess.PIPE).stdout
        normalized=b"\n".join(x for x in ddl.splitlines() if not x.startswith((b"\\restrict ",b"\\unrestrict ")))
        check(hashlib.sha256(normalized).hexdigest()==proof["schema_sha256"],"168-restored-full-schema-differs")
        results=[]
        for _ in range(2):
            results.append(boot(engine,active,support,invoices))
            check(audit()==expected and tree()==physical,"168-cold-boot-changed-the-originals")
        check(results[0]==results[1],"168-cold-boots-differ")
    finally:
        call("postgres",["pg_ctl","-D",GUEST/"postgres/cluster","-m","fast","-w","stop"],stdout=subprocess.DEVNULL)
    result={**summary,"recovery":DB,"original_rows_sequences_and_schema":True,"role_boots":2,"source_code_files":runtime_files,
            "overlay_files":addon_files,"operator_invoices_per_boot":42,"ticket_files_per_boot":418,"guest_files_per_boot":2,
            "expense_and_report_forms_per_boot":2,"wizard_fields":4,"workflows_sha256":results[0],"private_cluster_stopped":True}
    (HOST/"restored.json").write_text(json.dumps(result,sort_keys=True,indent=2))
    return result


if __name__=="__main__":
    if sys.argv[1:2]==["service"]:
        control=argparse.ArgumentParser(description="Reopen or stop the verified local 168 recovery cluster.")
        control.add_argument("action",choices=("start","stop"))
        with open("/dev/shm/steps-shared-qa-restore.lock","a+b") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if control.parse_args(sys.argv[2:]).action=="start":
                print(json.dumps(reopen_verified_cluster()))
            else:
                stop_verified_cluster()
        raise SystemExit(0)
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("base","h3","fiscal","payments","folder"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--sha256",required=True)
    opts=parser.parse_args()
    with open("/dev/shm/steps-shared-qa-restore.lock","a+b") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        print(json.dumps(recover(opts)))
