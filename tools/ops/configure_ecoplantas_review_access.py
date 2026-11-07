"""Configure an explicitly requested demo login; secrets arrive only on stdin.

Prove native forms and password verification in the disposable copy first.
Preserve source credentials and existing demo administrator permissions.
Never send an invitation or log a username/password.
"""
import fcntl
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import tempfile
import xmlrpc.client

from provision_ecoplantas_demo import ROOT, DB, COPY, USER, odoo, private_json, query


SCRIPT='''
import json
from pathlib import Path
from odoo import Command
from odoo.tools import config
previous=config['test_enable'];config['test_enable']=True
try:
    from odoo.tests import Form
finally:config['test_enable']=previous
request=json.loads(Path(REQUEST_PATH).read_text())
assert env.cr.dbname in ('ECOPLANTAS','ECOPLANTAS_T176_QA')
company=env.ref('base.main_company')
assert company.name=='ECOPLANTAS'
context=dict(env.context,no_reset_password=True,tracking_disable=True,mail_notrack=True,
    mail_create_nosubscribe=True,mail_notify_force_send=False,mail_auto_subscribe_no_notify=True)
users=env['res.users'].with_context(context,active_test=False)
account=users.search([('login','=',request['login'])])
assert len(account)<=1
groups=env['res.groups'].browse([env.ref(name).id for name in ('base.group_user','sales_team.group_sale_manager',
    'purchase.group_purchase_manager','stock.group_stock_manager','account.group_account_manager')])
if not COMMIT and not account:
    account=users.create({'login':request['login'],'email':request['login'],'name':'Revisión portal ECOPLANTAS',
        'company_id':company.id,'company_ids':[Command.set(company.ids)],
        'groups_id':[Command.set(env.ref('base.group_portal').ids)]})
if not account:
    account=users.create({'login':request['login'],'email':request['login'],
        'name':'Revisión ECOPLANTAS','company_id':company.id,'company_ids':[Command.set(company.ids)],
        'groups_id':[Command.set(groups.ids)],'lang':'es_CL','tz':'America/Santiago',
        'password':request['password']})
elif not SKIP_WRITE:
    assert account.company_id==company and account.company_ids==company
    scoped=(account.groups_id-env.ref('base.group_portal')-env.ref('base.group_public'))|groups
    account.write({'password':request['password'],'active':True,'groups_id':[Command.set(scoped.ids)]})
assert not account.share and account.has_group('base.group_user')
auth=account.with_user(account)._check_credentials({'type':'password','password':request['password']},{'interactive':True})
assert auth['uid']==account.id
business=env(user=account,su=False,context=dict(env.context,allowed_company_ids=company.ids))
Form(business['sale.order']);Form(business['purchase.order'])
Form(business['account.move'].with_context(default_move_type='out_invoice'))
visible=business['ir.ui.menu']._visible_menu_ids()
assert env.ref('sale.sale_menu_root').id in visible and env.ref('stock.menu_stock_root').id in visible
result={'user_id':account.id,'native_password_verified':True,'menus_and_forms':True,
        'company_scope':True,'internal_user':True,'committed':COMMIT}
# Odoo creates an automatic security email when a password is changed. The
# demo has no outgoing deliveries; retain that audit record in canceled state.
from odoo.tools import email_split
pending=env['mail.mail'].search([('create_date','>=',BACKUP_STAMP),('state','=','outgoing')])
for message in pending:
    if set(email_split(message.email_to or ''))=={request['login']}:
        message.write({'state':'cancel'})
if COMMIT:
    env.cr.commit()
    # The configuration shell and the HTTP service have separate registries.
    # Publish group-cache invalidation so an existing portal login sees its apps.
    env.registry.clear_cache()
    env.registry.signal_changes()
else:env.cr.rollback()
print('ECOPLANTAS_REVIEW_ACCESS_PROOF '+json.dumps(result))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    assert os.geteuid()==0 and (ROOT/'published.json').is_file()
    request=json.load(__import__('sys').stdin)
    assert isinstance(request['login'],str) and '@' in request['login']
    assert isinstance(request['password'],str) and 1<=len(request['password'])<=256
    request['login']=request['login'].strip().lower()
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        source_sql="SELECT md5(string_agg(id::text||coalesce(password,''),'' ORDER BY id)) FROM res_users"
        source_before=query('LAB_TAREAS',source_sql)
        existing=query(DB,"SELECT coalesce(json_agg(row_to_json(u)),'[]'::json) FROM (SELECT id,login,password,active FROM res_users) u")
        backup=ROOT/'review-access-before.json'
        if args.resume:assert backup.exists()
        else:
            assert not backup.exists(),'Preserve the original access backup'
            private_json(backup,json.loads(existing))
        stamp=datetime.fromtimestamp(backup.stat().st_mtime,timezone.utc).replace(tzinfo=None).isoformat(' ')
        identity=pwd.getpwnam(USER)
        with tempfile.NamedTemporaryFile(mode='w',dir=ROOT,prefix='.review-access-',delete=False) as stream:
            json.dump(request,stream);path=Path(stream.name)
        path.chmod(0o600);os.chown(path,identity.pw_uid,identity.pw_gid)
        try:
            proofs=[]
            for database,commit in ((COPY,False),(DB,True)):
                mail_sql="SELECT (SELECT count(*) FROM mail_mail WHERE state IN ('outgoing','sent','exception'))::text||':'||(SELECT count(*) FROM mail_notification)::text"
                before=tuple(map(int,query(database,mail_sql).split(':')))
                header='REQUEST_PATH='+repr(str(path))+'\nCOMMIT='+repr(commit)+'\n'
                header+='SKIP_WRITE='+repr(args.resume and commit)+'\nBACKUP_STAMP='+repr(stamp)+'\n'
                result=odoo(database,['--log-level=error'],script=header+SCRIPT)
                lines=[line for line in result.stdout.splitlines() if line.startswith('ECOPLANTAS_REVIEW_ACCESS_PROOF ')]
                assert len(lines)==1
                proofs.append(json.loads(lines[0].split(' ',1)[1]))
                after=tuple(map(int,query(database,mail_sql).split(':')))
                assert after[0]<=before[0] and after[1]==before[1]
            uid=xmlrpc.client.ServerProxy('https://ecoplantas.stepsapp.cl/xmlrpc/2/common').authenticate(DB,request['login'],request['password'],{})
            assert uid==proofs[-1]['user_id']
            assert query('LAB_TAREAS',source_sql)==source_before
            private_json(ROOT/'review-access-verified.json',{'copy':proofs[0],'live':proofs[1],
                'https_authenticated':True,'development_credentials_unchanged':True,'no_notifications':True})
            print('ECOPLANTAS_REVIEW_ACCESS_READY user_id='+str(uid)+' HTTPS_AUTHENTICATED NO_NOTIFICATIONS_OK',flush=True)
        finally:path.unlink(missing_ok=True)


if __name__=='__main__':main()
