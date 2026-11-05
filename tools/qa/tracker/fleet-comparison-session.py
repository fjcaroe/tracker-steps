"""Ephemeral native administrator session for read-only comparison review."""
import json
import os
from pathlib import Path
from odoo import http

assert env.cr.dbname in ('LAB_TAREAS', 'CERRO_EL_PLOMO')
proof = Path(os.environ['FLEET_COMPARISON_PROOF'])
assert proof.parent == Path('/tmp') and proof.name.startswith('personal-session-comparison-')
user = env['res.users'].browse(int(os.environ.get('FLEET_COMPARISON_USER', env.ref('base.user_admin').id))).exists()
assert len(user) == 1 and user.active and not user.share and user.has_group('base.group_system')
if os.environ.get('FLEET_COMPARISON_CLEANUP') == '1':
    data = json.loads(proof.read_text())
    session = http.root.session_store.get(data['session_id'])
    assert session.get('db') == env.cr.dbname and session.get('uid') == user.id
    http.root.session_store.delete(session)
    proof.unlink()
    print('FLEET_COMPARISON_SESSION_REMOVED')
else:
    assert not proof.exists()
    company = env['res.company'].browse(int(os.environ.get('FLEET_COMPARISON_COMPANY', user.company_id.id))).exists()
    assert len(company) == 1
    assert company in user.company_ids
    session = http.root.session_store.new()
    session.update({
        'db': env.cr.dbname, 'uid': user.id, 'login': user.login,
        'context': dict(user.with_user(user).context_get(), allowed_company_ids=company.ids),
        'session_token': user._compute_session_token(session.sid),
    })
    http.root.session_store.save(session)
    host = 'desarrollo.stepsapp.cl' if env.cr.dbname == 'LAB_TAREAS' else 'cerroelplomo.stepsapp.cl'
    proof.write_text(json.dumps({'session_id': session.sid, 'company_id': company.id, 'host': host}))
    proof.chmod(0o600)
    print('FLEET_COMPARISON_SESSION_READY')
env.cr.rollback()
