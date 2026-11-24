"""Pure guards shared by Harvest static certification, review and publication."""
import re


SUPPORTED_VERSIONS = ('0.0.3', '0.0.4', '0.0.5', '0.0.6', '0.0.7', '0.0.8')
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
OPERATIONS_REVIEW_CHECKS = (
    'crew_native_type_contractor', 'worker_enrollment', 'crew_attendance',
    'attendance_home_total', 'ot_close', 'ot_review', 'ot_send_confirmation',
    'native_copy_sync', 'sync_idempotency', 'pending_preserved', 'mobile_layout',
)
OPERATIONS_WRITE_PATHS = (
    '/api/harvest/sync', '/api/harvest/crew/sync', '/api/harvest/orders/transition',
)


def require_authorized_environment(frontend, environment):
    assert frontend['version'] in SUPPORTED_VERSIONS, 'Unsupported Harvest version'
    assert environment in ('development', 'cerro', 'qa-cerro'), 'Unsupported Harvest destination'
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


def validate_operations_copy(frontend, environment, stage_name, proof):
    require_authorized_environment(frontend, environment)
    assert frontend['version'] == '0.0.8'
    assert re.fullmatch('[a-f0-9]{40}', frontend['commit'])
    assert re.fullmatch('[a-f0-9]{40}', proof['commit'])
    assert re.fullmatch('[a-f0-9]{64}', proof['release_sha256'])
    run_id = 't236237_' + proof['commit'][:8]
    assert stage_name == 'management_' + environment + '_' + run_id
    assert proof['database'] == 'MANAGEMENT_QA_' + environment.upper() + '_' + run_id
    assert proof['feature'] == 'harvest-app' and proof['environment'] == environment
    assert proof['business_preserved'] is True
    assert not proof.get('readonly_copy'), 'Operations require a freshly upgraded native copy'


def validate_operations_review(frontend, environment, stage_name, proof, review):
    validate_operations_copy(frontend, environment, stage_name, proof)
    assert review['reviewed'] is True
    assert review['web_commit'] == frontend['commit']
    assert review['backend_commit'] == proof['commit']
    assert review['backend_sha256'] == proof['release_sha256']
    assert review['database'] == proof['database']
    assert all(review[key] is True for key in OPERATIONS_REVIEW_CHECKS), 'Incomplete crew/lifecycle review'


def validate_operations_smokes(frontend, proof, operations, crew):
    for result in (operations, crew):
        assert result['feature'] == proof['feature'] == 'harvest-app'
        assert result['database'] == proof['database']
        assert result['backend_commit'] == proof['commit']
        assert result['backend_sha256'] == proof['release_sha256']
        assert result['web_commit'] == frontend['commit']
        assert result['native_context'] is True
        assert result['credentials_or_session_ids_supplied'] is False
    assert all(operations[key] is True for key in (
        'native_copy_sync', 'sync_idempotency', 'ot_close', 'ot_review',
        'ot_send_confirmation', 'erp_state_preserved', 'unconfirmed_delivery_blocks_close'))
    assert all(crew[key] is True for key in (
        'worker_enrollment', 'crew_attendance', 'attendance_home_total',
        'native_members_preserved', 'enrollment_idempotency', 'attendance_idempotency',
        'changed_hours_rejected', 'wrong_date_rejected'))


def require_copy_sync_certificate(frontend, environment, stage_name, proof):
    if frontend['version'] == '0.0.8':
        validate_operations_copy(frontend, environment, stage_name, proof)
    else:
        assert frontend['version'] == '0.0.7', 'Copy writes require a certified Harvest copy'
        validate_static_copy(frontend, environment, stage_name, proof)


def is_copy_sync_request(enabled, method, path, origin, port, version='0.0.7'):
    paths = OPERATIONS_WRITE_PATHS if version == '0.0.8' else ('/api/harvest/sync',)
    return (enabled is True and method == 'POST' and path in paths
            and origin == 'http://127.0.0.1:' + str(port))
