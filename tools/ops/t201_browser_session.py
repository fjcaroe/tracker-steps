"""Create/remove a private native session for T201 read-only browser review."""
import json
import os
from pathlib import Path
from odoo import http
from native_business_profile import scoped_business_environment

hosts = {'LAB_TAREAS': 'desarrollo.stepsapp.cl', 'CERRO_EL_PLOMO': 'cerroelplomo.stepsapp.cl',
         'QA-CERROELPLOMO': 'qa-cerroelplomo.stepsapp.cl'}
assert env.cr.dbname in hosts
proof = Path(os.environ['T201_BROWSER_PROOF'])
assert proof.parent == Path('/tmp') and proof.name.startswith('t201-browser-')
if os.environ.get('T201_CLEANUP') == '1':
    data = json.loads(proof.read_text())
    session = http.root.session_store.get(data['session_id'])
    assert session.get('db') == env.cr.dbname
    http.root.session_store.delete(session)
    proof.unlink()
    print('T201_BROWSER_SESSION_REMOVED')
else:
    assert not proof.exists()
    business = scoped_business_environment(env)
    requested_company = int(os.environ.get('T201_COMPANY_ID') or 0)
    if requested_company:
        company = env['res.company'].search([('id', '=', requested_company), ('id', 'child_of', business.company.id)])
        assert len(company) == 1, 'Review must remain inside the destination business'
        business = scoped_business_environment(env, company=company)
    user = business.user
    session = http.root.session_store.new()
    session.update({'db': env.cr.dbname, 'uid': user.id, 'login': user.login,
        'context': dict(user.with_user(user).context_get(), allowed_company_ids=business.company.ids),
        'session_token': user._compute_session_token(session.sid)})
    http.root.session_store.save(session)
    actions = {'dashboard': business.ref('step_packing_operations.action_packing_dashboard').id}
    proof.write_text(json.dumps({'session_id': session.sid, 'company_id': business.company.id,
        'host': hosts[env.cr.dbname], 'actions': actions}))
    proof.chmod(0o600)
    print('T201_BROWSER_SESSION_READY')
env.cr.rollback()
