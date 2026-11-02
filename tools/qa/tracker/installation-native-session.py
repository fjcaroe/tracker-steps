"""Ephemeral native-account session for read-only installation verification."""
import json, os
from pathlib import Path
from odoo import http

facts = json.loads(Path(os.environ['INSTALLATION_FACTS']).read_text())
assert env.cr.dbname == 'CERRO_EL_PLOMO'
user = env['res.users'].browse(facts['source_user_id']).exists()
assert user.active and user.login == facts['login']
company = env['res.company'].browse(facts['company_id'])
assert company in user.company_ids
links = env['step.tracker.asset.link'].with_user(user).with_context(
    allowed_company_ids=company.ids).search([
        ('company_id', '=', company.id), ('asset_id', '=', facts['asset_id']),
        ('active', '=', True)])
assert len(links) == 1 and links.vehicle_id.license_plate == facts['plate']
session = http.root.session_store.new()
session.update(dict(db=env.cr.dbname, login=user.login, uid=user.id,
    context=dict(user.with_user(user).context_get(), allowed_company_ids=company.ids),
    session_token=user._compute_session_token(session.sid)))
http.root.session_store.save(session)
proof = Path(os.environ['INSTALLATION_SESSION_PROOF'])
assert proof.parent == Path('/tmp') and proof.name.startswith('personal-session-')
proof.write_text(json.dumps(dict(session_id=session.sid, company_id=company.id,
    host='cerroelplomo.stepsapp.cl')))
proof.chmod(0o600)
env.cr.rollback()
print('INSTALLATION_NATIVE_SESSION_READY')
