"""Create/remove a private native session for read-only T241 acceptance.

Odoo-shell caller supplies PLAN, RESULT, PROOF_PATH and CLEANUP. No credentials
or permissions are changed. The session file is private and never printed.
"""
import json
from pathlib import Path
from odoo import http
from native_business_profile import scoped_existing_user_environment

assert env.cr.dbname=='CERRO_EL_PLOMO' and PLAN['ticket']==241
proof=Path(PROOF_PATH)
assert proof.parent==Path('/tmp') and proof.name.startswith('t241-browser-')
if CLEANUP:
    saved=json.loads(proof.read_text())
    session=http.root.session_store.get(saved['session_id'])
    assert session.get('db')==env.cr.dbname and session.get('uid')==PLAN['user_id']
    http.root.session_store.delete(session);proof.unlink()
    print('T241_BROWSER_SESSION_REMOVED')
else:
    assert not proof.exists()
    business=scoped_existing_user_environment(env,PLAN['user_id'],env['res.company'].browse(PLAN['company_id']))
    user=business.user
    session=http.root.session_store.new()
    session.update({'db':env.cr.dbname,'uid':user.id,'login':user.login,
        'context':dict(user.with_user(user).context_get(),allowed_company_ids=business.company.ids),
        'session_token':user._compute_session_token(session.sid)})
    http.root.session_store.save(session)
    proof.write_text(json.dumps({'session_id':session.sid,'company_id':business.company.id,
        'host':'cerroelplomo.stepsapp.cl','receipts':RESULT['receipts'],'tags':RESULT['tags'],
        'drafts':RESULT['drafts'],'packaging':PLAN['new_packaging'],
        'actions':{'receipts':business.ref('step_packing_operations.menu_packing_reception_process').action.id,
                   'tags':business.ref('step_inventory_packing.menu_steps_fruit_packages').action.id,
                   'drafts':business.ref('step_producer_advances.action_advance_proformas').id}}))
    proof.chmod(0o600)
    print('T241_BROWSER_SESSION_READY')
env.cr.rollback()
