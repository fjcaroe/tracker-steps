"""Admit the original Steps modules available at their stored version in the sealed free runtime."""
import ast
import hashlib
import json
from pathlib import Path
import re


RUNTIME = Path('/opt/steps-validation/community-foundation-final-20261027/community-runtime')
FREE = {'LGPL-3', 'GPL-3', 'AGPL-3'}
SOURCE_INVENTORY = '394d9163d2cbf1906df71ef17a69305c2f54e60870f9fddbe716a9aa280f6639'
SOURCE_MANIFESTS = '0146e9a78d75ed0b33c943505cc3c1a3026f7fd15d2a5ec0c6198087465cd210'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def prepare(cr):
    cr.execute('SELECT current_database()')
    database, = cr.fetchone()
    if not re.fullmatch(r'COMMUNITY_STEPS_CRM_[A-Z0-9_]+', database):
        raise ValueError('Use a private Steps CRM restore.')
    cr.execute("SELECT name,latest_version,license FROM ir_module_module WHERE state='installed' ORDER BY name FOR UPDATE")
    installed = cr.fetchall()
    if digest(installed) != SOURCE_INVENTORY:
        raise ValueError('The original Steps inventory changed.')
    cr.execute("SELECT count(*) FROM ir_module_module WHERE state LIKE 'to %'")
    if cr.fetchone() != (0,):
        raise ValueError('A module operation is pending.')
    candidates, manifests = {}, {}
    for name, stored, license_name in installed:
        if license_name not in FREE:
            continue
        sources = [root / name / '__manifest__.py' for root in (RUNTIME / 'addons', RUNTIME / 'odoo/addons')]
        source = next((path for path in sources if path.is_file()), None)
        if not source:
            continue
        body = source.read_bytes()
        manifest = ast.literal_eval(body.decode())
        version = manifest.get('version', '1.0')
        if not version.startswith('18.0.'):
            version = '18.0.' + version
        if version != stored or manifest.get('license', 'LGPL-3') != license_name or not manifest.get('installable', True):
            continue
        candidates[name] = set(manifest.get('depends', [] if name == 'base' else ['base']))
        manifests[name] = hashlib.sha256(body).hexdigest()
    cr.execute("""SELECT m.name,d.name FROM ir_module_module m
                  JOIN ir_module_module_dependency d ON d.module_id=m.id
                  WHERE m.name=ANY(%s)""", [sorted(candidates)])
    for name, dependency in cr.fetchall():
        candidates[name].add(dependency)
    keep = set(candidates)
    while True:
        closed = {name for name in keep if candidates[name] <= keep}
        if closed == keep:
            break
        keep = closed
    manifest_digest = digest({n: manifests[n] for n in keep})
    if len(keep) != 157 or manifest_digest != SOURCE_MANIFESTS:
        raise ValueError('The Steps sales dependencies differ from the sealed inventory.')
    excluded = sorted(name for name, _, _ in installed if name not in keep)
    cr.execute("UPDATE ir_module_module SET state='uninstalled' WHERE state='installed' AND name=ANY(%s)", [excluded])
    if cr.rowcount != len(excluded):
        raise ValueError('Unexpected number of excluded source modules.')
    return {'database': database, 'original': len(installed), 'enabled': sorted(keep), 'excluded': excluded,
            'source_inventory_sha256': SOURCE_INVENTORY, 'source_manifest_sha256': manifest_digest}
