"""Verify the previous Steps flows and retain the final Projects snapshot."""
import argparse
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

from restore_local_steps_project import TARGET,capture,inventory,PACKAGE,PARENT
from restore_local_steps_expense_credit import HOST,GUEST,call,pg
from verify_converted_backup import check,hash_file


TOOLS=Path(__file__).resolve().parent
EVIDENCE=('U51ProjectQ-functional.json','U51ProjectQ-preservation.json','U51ProjectQ-install.json','U51ProjectQ-update.json')


def normalized(data):
    return json.dumps(data,sort_keys=True,separators=(',',':')).encode()


def seal(evidence,out):
    work=HOST/'project-qualification'
    scope=GUEST/'project-qualification'
    original=evidence/'U50E-steps-168-cold'
    check(hash_file(original/'checkpoint.json')==PARENT,'unexpected-project-backup-parent')
    out.mkdir(exist_ok=True)
    index=out/'checkpoint.json'
    if index.exists():
        existing=json.loads(index.read_bytes())
        check(existing['parent']==PARENT and existing['package']==PACKAGE and
              all(Path(n).name==n and hash_file(out/n)==v for n,v in existing['sha256'].items()),
              'different-existing-project-backup')
        print(hash_file(index))
        return
    with tarfile.open(original/'functional-evidence.tar') as arc:
        expected=[json.load(arc.extractfile(n))[k] for n,k in (
            ('U50FullFiscal-steps-invoice-text-fiscal.json','documents'),('support-integrated.json','thread'))]
    args=json.loads((work/'args.json').read_bytes())
    check(args[args.index('-d')+1]==TARGET and '--no-http' in args,'wrong-project-backup-runtime')
    for name in ('probe_steps_fiscal_invoice_text','probe_sys_retained_provider_release','probe_steps_support_thread'):
        shutil.copyfile(TOOLS/(name+'.py'),work/'code'/(name+'.py'))
    script=f"import json,sys\nsys.path[:0]=[{str(scope/'code')!r},{str(GUEST/'tools')!r}]\n"
    script+="""
from probe_steps_fiscal_invoice_text import run
from probe_steps_support_thread import internal,portal
def operator(uid):
 user=env['res.users'].browse(uid)
 return env(user=uid,su=False,context={'allowed_company_ids':[user.company_id.id],'lang':user.lang,'tracking_disable':True,'bin_size':False,'mail_notify_force_send':False})
tax=run(env)['documents']
env.cr.execute('SET TRANSACTION READ ONLY')
users=[operator(i) for i in (7,10)]
visitor=operator(6)
tickets=users[0]['helpdesk.ticket'].search([],order='id').ids
visible=visitor['helpdesk.ticket'].search([],order='id').ids
assert len(tickets)==243 and len(visible)==5
threads={'operators':[internal(actor,tickets) for actor in users], 'portal':portal(visitor,operator(env.ref('base.public_user').id),visible,next(t for t in tickets if t not in visible))}
print('PROOF '+json.dumps([tax,threads]))
env.cr.rollback()
"""
    with open('/dev/shm/steps-shared-qa-restore.lock','a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        before,defs=capture(TARGET)
        tree=inventory(work/'data/filestore'/TARGET)
        proc=call('odoo',args,input=script.encode(),capture_output=True)
        observed=[json.loads(row[6:]) for row in proc.stdout.splitlines() if row.startswith(b'PROOF ')]
        check(observed==[expected],'invoice-or-ticket-reads-changed-after-projects')
        with (out/'source.dump').open('xb') as dump:
            pg('pg_dump','-Fc','--no-tablespaces','-d',TARGET,stdout=dump)
        check(capture(TARGET)==[before,defs] and tree==inventory(work/'data/filestore'/TARGET),
              'project-rows-schema-or-files-changed-during-seal')
        for name,data in [('snapshot',before),('sql-objects',defs),('filestore',tree)]:
            (out/(name+'.json.gz')).write_bytes(gzip.compress(normalized(data),mtime=0))
        (out/'evidence.json').write_bytes(normalized({n:hash_file(evidence/n) for n in EVIDENCE}))
        info={'parent':PARENT,'package':PACKAGE,'rows':sum(v[0] for v in before['public_tables'].values()),
              'tables':len(before['public_tables']),'sequences':len(before['sequence_values']),'sql_objects':len(defs),
              'files':len(tree),'invoices':len(expected[0]),'ticket_files':418,'guest_ticket_files':2,
              'sha256':{item.name:hash_file(item) for item in out.iterdir() if item!=index}}
        index.write_bytes(normalized(info))
        print(hash_file(index))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('evidence','destination'):
        parser.add_argument(arg,type=Path)
    opts=parser.parse_args()
    seal(opts.evidence,opts.destination)
