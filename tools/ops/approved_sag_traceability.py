"""Promote only the exact T93/T94 content approved after Development review."""
import json
from pathlib import Path
import re
import hashlib

MODULES = ('step_packing_operations', 'step_packing_dispatch', 'step_packing_sag', 'step_export_traceability')
APPROVED_RELEASES = {
    'bfc2430f5b593f399a5774e8251ea79c21df3997': MODULES[:3],
    '32b884ede0e87503f7ce3f1883ca1876e5e4b87e': MODULES[3:],
}
DEVELOPMENT_RELEASES = Path('/opt/steps-managed/releases/development')


def verify_content(proof):
    """Require equality of every approved file, version and module, not a branch name."""
    expected_files, versions = {}, {}
    for commit, modules in APPROVED_RELEASES.items():
        source = json.loads((DEVELOPMENT_RELEASES / commit / 'release.json').read_text())
        assert source['commit'] == commit
        expected_files.update({name: sha for name, sha in source['files'].items() if name.split('/')[0] in modules})
        for name, sha in source['files'].items():
            if name.split('/')[0] in modules:
                original = DEVELOPMENT_RELEASES / commit / name
                assert hashlib.sha256(original.read_bytes()).hexdigest() == sha
        versions.update({name: source['versions'][name] for name in modules})
    assert proof['files'] == expected_files, 'Content differs from approved T93/T94 packages'
    assert proof['versions'] == versions


def verify_authorization(directory, development_proof, proof, release_sha):
    assert directory and development_proof, 'Cerro requires recorded human approvals and exact Development test proof'
    for ticket, message in ((93, 9521), (94, 9518)):
        item = json.loads((directory / (str(ticket) + '.json')).read_text(encoding='utf-8-sig'))
        assert item['ticket']['id'] == ticket
        replies = [m for m in item['messages'] if m['message_type'] in ('comment', 'email')]
        latest = max(replies, key=lambda m: m['id'])
        assert latest['id'] == message, 'Read newer human responses before promotion'
        body = re.sub('<[^>]+>', ' ', latest['body']).lower()
        assert 'aprobad' in body and 'cerro el plomo' in body
    test = json.loads(development_proof.read_text())
    assert test['database'].startswith('MANAGEMENT_QA_DEVELOPMENT_')
    assert test['commit'] == proof['commit'] and test['release_sha256'] == release_sha
    verify_content(proof)
