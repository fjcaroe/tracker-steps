"""Bind observed browser, native, and copy-flow results for T244/T245."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from harvest_web_policy import validate_operations_review, validate_operations_smokes


def read(path):
    return json.loads(path.read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('base', type=Path)
    p.add_argument('environment', choices=('development', 'cerro', 'qa-cerro'))
    p.add_argument('mode', choices=('copy', 'live'))
    p.add_argument('browser', type=Path)
    p.add_argument('--flow', type=Path)
    a = p.parse_args()
    manifest = read(a.base / 'web/release.json')
    assert manifest['version'] == '0.0.12'
    release = read(a.base / 'backend-release.json')
    stage = a.base.parent / ('management_' + a.environment + '_t244245_' + release['commit'][:8])
    qa = read(stage / 'qa_passed.json')
    browser = read(a.browser)
    assert browser['version'] == manifest['version'] and browser['server_writes'] is False
    assert all(browser[key] is True for key in ('native_context', 'native_weight_form', 'harvest_launcher',
        'packaging_selector', 'standard_weight_readonly', 'manual_weight_hundredths', 'mobile_layout',
        'capture_without_tarja', 'worker_tarja_association_off', 'ot_native_fields', 'pass_required',
        'ot_work_hours', 'day_allocation'))
    native_log = (stage / ('verify-' + qa['database'] + '.log')) if a.mode == 'copy' else a.base / ('deploy-' + a.environment + '.log')
    text = native_log.read_text()
    native = json.loads(re.findall(r'MANAGEMENT_REGISTRY_OK (\{[^\n]+\})', text)[-1])
    assert all(native[key] is True for key in ('native_masters', 'existing_records_web_read',
        'harvest_tariff_menu_form', 'harvest_tariff_center_scope', 'harvest_api_context_scope',
        'harvest_mobile_lifecycle_form', 'harvest_crew_attendance_menu_form'))
    result = {**browser, 'environment': a.environment, 'web_commit': manifest['commit'],
        'backend_commit': qa['commit'], 'backend_sha256': qa['release_sha256'], 'database': qa['database'],
        'tariff_form': True, 'native_centers': True, 'harvest_menu': True,
        'ot_lifecycle_available': True, 'crew_attendance_available': True, 'reviewed': True}
    if a.mode == 'copy':
        assert a.flow
        flow = read(a.flow)
        for key, value in (('environment', a.environment), ('database', qa['database']), ('web_commit', manifest['commit'])):
            assert flow[key] == value
        assert all(flow[key] is True for key in ('client_close_with_hours', 'client_approval_send',
            'client_native_fields', 'client_reload_preserved', 'native_cost_hours'))
        operations = read(stage / 'harvest-operations-smoke.json')
        crew = read(stage / 'harvest-crew-smoke.json')
        validate_operations_smokes(manifest, qa, operations, crew)
        result.update({key: value for source in (operations, crew) for key, value in source.items() if value is True})
        result.update({key: value for key, value in flow.items() if value is True})
        assert operations['existing_relations_only'] and browser['local_weight_preserved']
        result.update({'no_sample_data': True, 'pending_preserved': True,
            'reviewed_messages': {236: 10650, 237: 10648, 242: 10673, 243: 10677, 244: 10692, 245: 10696},
            'operations_smoke_sha256': hashlib.sha256((stage / 'harvest-operations-smoke.json').read_bytes()).hexdigest(),
            'crew_smoke_sha256': hashlib.sha256((stage / 'harvest-crew-smoke.json').read_bytes()).hexdigest()})
        validate_operations_review(manifest, a.environment, stage.name, qa, result)
        output = stage / 'harvest-browser-proof.json'
    else:
        web = read(stage / 'harvest-web-deployed.json')
        assert web['web_commit'] == manifest['commit'] and web['served'] == manifest['files']
        assert 'MANAGEMENT_VERIFY_OK' in text and web['backend_commit'] == qa['commit']
        output = a.base / (a.environment + '-live-review.json')
    output.write_text(json.dumps(result, indent=2))
    output.chmod(0o600)
    print('HARVEST_HOURS_REVIEW_VERIFIED ' + a.mode + ' ' + a.environment)


if __name__ == '__main__':
    main()
