import hashlib
import json
from pathlib import Path
import sys

stage, browser = map(Path, sys.argv[1:])
assert stage.resolve() == stage and stage.parent == Path('/opt/steps-validation')
proof = json.loads((stage / 'qa_passed.json').read_text())
policy = json.loads((stage / 'harvest-review-policy.json').read_text())
web = policy['harvest_web']
operations_path = stage / 'harvest-operations-smoke.json'
crew_path = stage / 'harvest-crew-smoke.json'
operations = json.loads(operations_path.read_text())
crew = json.loads(crew_path.read_text())
ui = json.loads(browser.read_text())
registry_lines = (stage / f"verify-{proof['database']}.log").read_text().splitlines()
registry = json.loads(next(line.partition(' ')[2] for line in registry_lines if line.startswith('MANAGEMENT_REGISTRY_OK ')))
assert registry['versions'] == proof['backend_versions']
assert ui['version'] == web['version'] and ui['native_context'] is True and ui['server_writes'] is False
assert ui['local_weight_preserved'] is True
assert ui['native_weight_form'] is True and ui['harvest_launcher'] is True
assert policy['copy_sync_allowed'] is True and policy['database'] == proof['database']

from harvest_web_policy import validate_operations_review, validate_operations_smokes

validate_operations_smokes(web, proof, operations, crew)
review = {**operations, **crew, **ui,
    'reviewed': True, 'reviewed_messages': {236: 10650, 237: 10648, 242: 10673},
    'tariff_form': registry['harvest_tariff_menu_form'], 'native_centers': registry['native_masters'],
    'harvest_menu': registry['harvest_api_context_scope'], 'no_sample_data': operations['existing_relations_only'],
    'crew_native_type_contractor': ui['crew_native_type_contractor'], 'pending_preserved': ui['local_weight_preserved'],
    'operations_smoke_sha256': hashlib.sha256(operations_path.read_bytes()).hexdigest(),
    'crew_smoke_sha256': hashlib.sha256(crew_path.read_bytes()).hexdigest(),
}
if web['version'] == '0.0.11':
    review['reviewed_messages'][243] = 10677
validate_operations_review(web, policy['environment'], stage.name, proof, review)
with (stage / 'harvest-browser-proof.json').open('x', encoding='utf-8') as stream:
    json.dump(review, stream, indent=2)
print('HARVEST_BROWSER_COPY_OK', policy['environment'], web['version'])
