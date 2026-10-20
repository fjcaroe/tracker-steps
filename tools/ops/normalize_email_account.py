"""Executed inside the backed-up, locked deployment for one explicitly requested user."""
import json
assert env.cr.dbname == EXPECTED_DATABASE == 'CERRO_EL_PLOMO'
user=env['res.users'].browse(APPROVED_USER_ID).exists()
assert len(user)==1 and user.login==EXPECTED_USER_LOGIN and '@' in user.login
assert env['ir.module.module'].search([('name','=','step_auth_email_casefold'),('state','=','installed')])
env.cr.execute('SELECT id FROM res_users WHERE id=%s FOR UPDATE', [user.id])
def preserved():
    env.flush_all()
    env.cr.execute("SELECT to_jsonb(u)-ARRAY['login','write_date','write_uid'] FROM res_users u WHERE id=%s",[user.id])
    record=env.cr.fetchone()[0]
    return (record,tuple(sorted(user.groups_id.ids)),tuple(sorted(user.company_ids.ids)))
before=preserved()
env.cr.execute('SELECT count(*) FROM mail_mail'); mails=env.cr.fetchone()[0]
env.cr.execute('SELECT count(*) FROM mail_notification'); notifications=env.cr.fetchone()[0]
user.with_context(tracking_disable=True,mail_notrack=True,no_reset_password=True,
    mail_create_nosubscribe=True,mail_auto_subscribe_no_notify=True).write({'login':user.login.lower()})
assert preserved()==before, 'Unexpected change to password or account access'
assert user.login==EXPECTED_USER_LOGIN.lower()
for value in (user.login.lower(),user.login.upper()):
    assert env['res.users'].search(env['res.users']._get_login_domain(value))==user
env.cr.execute('SELECT count(*) FROM mail_mail'); assert env.cr.fetchone()[0]==mails
env.cr.execute('SELECT count(*) FROM mail_notification'); assert env.cr.fetchone()[0]==notifications
env.cr.commit()
print('EMAIL_ACCOUNT_NORMALIZED_OK '+json.dumps({'user_id':user.id,'lowercase':True,
    'password_and_access_unchanged':True,'no_mail_notifications':True}))
