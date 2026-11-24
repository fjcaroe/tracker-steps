"""Pure guards shared by Harvest static certification, review and publication."""
import re


SUPPORTED_VERSIONS = ('0.0.3', '0.0.4', '0.0.5', '0.0.6', '0.0.7')
STATIC_FEATURES = {
    '0.0.4': ('harvestcompany', 'harvest-company-selector'),
    '0.0.7': ('harvestandroid', 'harvest-android-pilot'),
}
ANDROID_REVIEW_CHECKS = (
    'company_selector', 'authorized_companies_only', 'company_round_trip',
    'pending_preserved', 'plot_selector', 'plots_filtered_by_center',
    'plot_selection_reset', 'plot_all_location_modes', 'mobile_layout',
    'pilot_capture', 'manual_capture', 'durable_storage',
    'native_copy_sync', 'sync_idempotency',
)


def require_authorized_environment(frontend, environment):
    assert frontend['version'] in SUPPORTED_VERSIONS, 'Unsupported Harvest version'
    if frontend['version'] == '0.0.7':
        assert environment == 'development', 'The Android pilot is authorized only in Desarrollo'


def static_copy_identity(frontend, environment):
    require_authorized_environment(frontend, environment)
    assert frontend['version'] in STATIC_FEATURES, 'This version requires its native backend certification'
    tag, feature = STATIC_FEATURES[frontend['version']]
    assert re.fullmatch('[a-f0-9]{40}', frontend['commit'])
    run_id = tag + '_' + frontend['commit'][:8]
    return run_id, feature


def validate_static_copy(frontend, environment, stage_name, proof):
    run_id, feature = static_copy_identity(frontend, environment)
    assert stage_name == 'management_' + environment + '_' + run_id
    assert proof['database'] == 'MANAGEMENT_QA_' + environment.upper() + '_' + run_id
    assert proof['feature'] == feature
    assert proof['readonly_copy'] is True and proof['business_preserved'] is True
    assert proof['harvest_web'] == frontend, 'The certified copy must bind the exact frontend files'
    assert re.fullmatch('[a-f0-9]{40}', proof['commit'])
    assert re.fullmatch('[a-f0-9]{64}', proof['release_sha256'])


def validate_android_review(frontend, environment, stage_name, proof, review):
    assert frontend['version'] == '0.0.7'
    validate_static_copy(frontend, environment, stage_name, proof)
    assert review['reviewed'] is True
    assert review['web_commit'] == frontend['commit']
    assert review['backend_commit'] == proof['commit']
    assert review['database'] == proof['database']
    assert review['backend_sha256'] == proof['release_sha256']
    assert all(review[key] is True for key in ANDROID_REVIEW_CHECKS), 'Incomplete Android pilot review'


def require_copy_sync_certificate(frontend, environment, stage_name, proof):
    assert frontend['version'] == '0.0.7', 'Copy sync is restricted to the Android pilot'
    validate_static_copy(frontend, environment, stage_name, proof)


def is_copy_sync_request(enabled, method, path, origin, port):
    return (enabled is True and method == 'POST' and path == '/api/harvest/sync'
            and origin == 'http://127.0.0.1:' + str(port))
