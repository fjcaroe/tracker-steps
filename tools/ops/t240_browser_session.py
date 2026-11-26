"""Create/remove a native session for read-only review of the approved T240 plan.

Odoo-shell caller supplies PLAN, PROOF_PATH and CLEANUP. Never logs the session,
changes credentials or grants permissions. Browser proof stays outside Git.
"""
import json
from pathlib import Path
from odoo import http
from native_business_profile import scoped_existing_user_environment

assert env.cr.dbname == 'CERRO_EL_PLOMO'
proof = Path(PROOF_PATH)
assert proof.parent == Path('/tmp') and proof.name.startswith('t240-browser-')
if CLEANUP:
    saved = json.loads(proof.read_text())
    session = http.root.session_store.get(saved['session_id'])
    assert session.get('db') == env.cr.dbname and session.get('uid') == PLAN['user_id']
    http.root.session_store.delete(session)
    proof.unlink()
    print('T240_BROWSER_SESSION_REMOVED')
else:
    assert not proof.exists()
    company = env['res.company'].browse(PLAN['company_id'])
    business = scoped_existing_user_environment(env, PLAN['user_id'], company)
    user = business.user
    session = http.root.session_store.new()
    session.update({'db': env.cr.dbname, 'uid': user.id, 'login': user.login,
        'context': dict(user.with_user(user).context_get(), allowed_company_ids=company.ids),
        'session_token': user._compute_session_token(session.sid)})
    http.root.session_store.save(session)
    draft = business['purchase.order'].browse([r['id'] for r in PLAN['draft_proformas']])
    receipt_menu = business.ref('step_packing_operations.menu_packing_reception_process')
    tag_menu = business.ref('step_inventory_packing.menu_steps_fruit_packages')
    advance_menu = business.ref('step_producer_advances.action_advance_proformas')
    proof.write_text(json.dumps({'session_id':session.sid, 'company_id':company.id,
        'host':'cerroelplomo.stepsapp.cl', 'tags':PLAN['tags'],
        'total_kg':PLAN['expected_after_total'],
        'actions':{'tags':tag_menu.action.id,'receipts':receipt_menu.action.id,'advances':advance_menu.id},
        'drafts':[{'id':d.id,'name':d.name,'total':d.amount_total} for d in draft]}))
    proof.chmod(0o600)
    print('T240_BROWSER_SESSION_READY')
env.cr.rollback()
