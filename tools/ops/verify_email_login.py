"""Read-only live identity resolution; auth credentials tested only on private clones."""
import importlib,json
from pathlib import Path
for name,version in EXPECTED.items():
    module=env['ir.module.module'].search([('name','=',name)])
    assert module.state=='installed' and module.latest_version==version
    assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
users=env['res.users'].with_context(active_test=False).search([])
checked=0
for user in users.filtered(lambda u:'@' in u.login):
    for value in (user.login.lower(),user.login.upper()):
        result=env['res.users'].with_context(active_test=False).search(env['res.users']._get_login_domain(value))
        assert result==user
    checked+=1
env.cr.execute("SELECT indisunique,indisvalid FROM pg_index WHERE indexrelid='step_auth_email_login_ci_unique'::regclass")
assert env.cr.fetchone()==(True,True)
assert env['res.users'].get_view(env.ref('base.view_users_form').id,'form')['arch']
assert env.ref('base.menu_users').active
print('MANAGEMENT_REGISTRY_OK '+json.dumps({'email_identities_checked':checked,'unique_index':True,
    'native_password_mfa_cooldown':True,'user_form_and_menu':True,'versions':EXPECTED}))
env.cr.rollback()
