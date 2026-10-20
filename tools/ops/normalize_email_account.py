"""Executed inside the backed-up, locked deployment for one explicitly requested user."""
import json
assert env.cr.dbname == EXPECTED_DATABASE
assert (EXPECTED_DATABASE == 'CERRO_EL_PLOMO' and NORMALIZE_COMMIT) or (EXPECTED_DATABASE.startswith('MANAGEMENT_QA_CERRO_') and not NORMALIZE_COMMIT)
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
mail_model=env['mail.mail'].sudo()
mail_ids_before=set(mail_model.search([]).ids)
env.cr.execute('SELECT count(*) FROM mail_notification'); notifications=env.cr.fetchone()[0]
user.with_context(tracking_disable=True,mail_notrack=True,no_reset_password=True,
    mail_create_nosubscribe=True,mail_auto_subscribe_no_notify=True).write({'login':user.login.lower()})
assert preserved()==before, 'Unexpected change to password or account access'
assert user.login==EXPECTED_USER_LOGIN.lower()
for value in (user.login.lower(),user.login.upper()):
    assert env['res.users'].search(env['res.users']._get_login_domain(value))==user
# Mail's native login-change notice ignores tracking flags. Keep its audit
# record cancelled before commit; never suppress future security notifications.
new_mails=mail_model.search([('id','not in',list(mail_ids_before))])
assert len(new_mails)<=1 and all(m.email_to==user.email_formatted for m in new_mails)
new_mails.write({'state':'cancel'})
assert all(m.state=='cancel' for m in new_mails)
assert set(mail_model.search([]).ids)==mail_ids_before | set(new_mails.ids)
env.cr.execute('SELECT count(*) FROM mail_notification'); assert env.cr.fetchone()[0]==notifications
env.cr.commit() if NORMALIZE_COMMIT else env.cr.rollback()
print(('EMAIL_ACCOUNT_NORMALIZED_OK ' if NORMALIZE_COMMIT else 'EMAIL_ACCOUNT_NORMALIZATION_TESTED_OK ')+json.dumps({'user_id':user.id,'lowercase':True,
    'password_and_access_unchanged':True,'no_outgoing_mail':True,'cancelled_case_only_notice_count':len(new_mails)}))
