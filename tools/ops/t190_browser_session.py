"""Create/remove a private native session for T190 read-only browser review."""
import json
import os
from pathlib import Path
from odoo import http
from native_business_profile import scoped_business_environment

hosts = {'LAB_TAREAS': 'desarrollo.stepsapp.cl', 'CERRO_EL_PLOMO': 'cerroelplomo.stepsapp.cl',
         'QA-CERROELPLOMO': 'qa-cerroelplomo.stepsapp.cl'}
assert env.cr.dbname in hosts
proof = Path(os.environ['T190_BROWSER_PROOF'])
assert proof.parent == Path('/tmp') and proof.name.startswith('t190-browser-')
if os.environ.get('T190_CLEANUP') == '1':
    data = json.loads(proof.read_text())
    session = http.root.session_store.get(data['session_id'])
    assert session.get('db') == env.cr.dbname
    http.root.session_store.delete(session)
    proof.unlink()
    print('T190_BROWSER_SESSION_REMOVED')
else:
    assert not proof.exists()
    business = scoped_business_environment(env)
    user = business.user
    session = http.root.session_store.new()
    session.update({'db': env.cr.dbname, 'uid': user.id, 'login': user.login,
        'context': dict(user.with_user(user).context_get(), allowed_company_ids=business.company.ids),
        'session_token': user._compute_session_token(session.sid)})
    http.root.session_store.save(session)
    actions = {name: business.ref(xmlid).id for name, xmlid in {
        'rfq': 'purchase.purchase_rfq', 'purchase': 'purchase.purchase_form_action',
        'fruit': 'step_packing_fruit_proforma.fruit_proforma_action',
        'advance': 'step_producer_advances.action_advance_proformas'}.items()}
    proof.write_text(json.dumps({'session_id': session.sid, 'company_id': business.company.id,
        'host': hosts[env.cr.dbname], 'actions': actions}))
    proof.chmod(0o600)
    print('T190_BROWSER_SESSION_READY')
env.cr.rollback()
