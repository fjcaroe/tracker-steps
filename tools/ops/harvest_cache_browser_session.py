"""Odoo-shell read-only session for the published Harvest cache acceptance.

Caller supplies PROOF_PATH and CLEANUP. Credentials, roles and records remain.
"""
import json
from pathlib import Path
from odoo import http
from native_business_profile import scoped_business_environment

hosts={'LAB_TAREAS':'desarrollo.stepsapp.cl','CERRO_EL_PLOMO':'cerroelplomo.stepsapp.cl',
       'QA-CERROELPLOMO':'qa-cerroelplomo.stepsapp.cl'}
assert env.cr.dbname in hosts
proof=Path(PROOF_PATH)
assert proof.parent==Path('/tmp') and proof.name.startswith('harvest-cache-browser-')
if CLEANUP:
    data=json.loads(proof.read_text());session=http.root.session_store.get(data['session_id'])
    assert session.get('db')==env.cr.dbname
    http.root.session_store.delete(session);proof.unlink()
    print('HARVEST_CACHE_SESSION_REMOVED')
else:
    assert not proof.exists()
    company=env['res.company'].browse(1) if env.cr.dbname!='LAB_TAREAS' else None
    business=scoped_business_environment(env,company=company)
    user=business.user;session=http.root.session_store.new()
    session.update({'db':env.cr.dbname,'uid':user.id,'login':user.login,
        'context':dict(user.with_user(user).context_get(),allowed_company_ids=business.company.ids),
        'session_token':user._compute_session_token(session.sid)})
    http.root.session_store.save(session)
    proof.write_text(json.dumps({'host':hosts[env.cr.dbname],'session_id':session.sid,'company_id':business.company.id}))
    proof.chmod(0o600)
    print('HARVEST_CACHE_SESSION_READY')
env.cr.rollback()
