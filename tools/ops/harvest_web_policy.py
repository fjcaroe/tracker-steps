"""Pure guards shared by Harvest static certification, review and publication."""
import re


SUPPORTED_VERSIONS = ('0.0.3', '0.0.4', '0.0.5', '0.0.6', '0.0.7', '0.0.8', '0.0.9', '0.0.10', '0.0.11', '0.0.12')
WEIGHT_VERSIONS = ('0.0.10', '0.0.11', '0.0.12')
REVISED_OPERATIONS_VERSIONS = ('0.0.9', *WEIGHT_VERSIONS)
OPERATIONS_VERSIONS = ('0.0.8', *REVISED_OPERATIONS_VERSIONS)
OPERATIONS_CASES = {
    '0.0.8': ('t236237', None), '0.0.9': ('t236237', '18.0.1.4.1'),
    '0.0.10': ('t242', '18.0.1.5.0'), '0.0.11': ('t243', '18.0.1.6.0'),
    '0.0.12': ('t244245', '18.0.1.7.0'),
}
V9_REVIEWED_MESSAGES = {236: 10650, 237: 10648}
STANDARD_WEIGHT_REVIEW_CHECKS = ('packaging_selector', 'standard_weight_readonly', 'manual_weight_hundredths')
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
OPERATIONS_V9_REVIEW_CHECKS = (*OPERATIONS_REVIEW_CHECKS,
    'ot_reopen_before_send', 'sent_ot_cannot_reopen', 'order_approver_selection',
    'native_approval', 'send_flushes_pending_deliveries', 'send_received_manifest',
    'harvest_attendance_cosecha_only',
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
    assert frontend['version'] in OPERATIONS_VERSIONS
    assert re.fullmatch('[a-f0-9]{40}', frontend['commit'])
    assert re.fullmatch('[a-f0-9]{40}', proof['commit'])
    assert re.fullmatch('[a-f0-9]{64}', proof['release_sha256'])
    ticket, version = OPERATIONS_CASES[frontend['version']]
    run_id = ticket + '_' + proof['commit'][:8]
    assert stage_name == 'management_' + environment + '_' + run_id
    assert proof['database'] == 'MANAGEMENT_QA_' + environment.upper() + '_' + run_id
    assert proof['feature'] == 'harvest-app' and proof['environment'] == environment
    assert proof['business_preserved'] is True
    assert not proof.get('readonly_copy'), 'Operations require a freshly upgraded native copy'
    if version:
        assert proof['backend_versions']['step_harvest_launcher'] == version, 'Harvest requires its matching native backend'


def validate_reviewed_messages(frontend, reviewed):
    if frontend['version'] in REVISED_OPERATIONS_VERSIONS:
        expected = dict(V9_REVIEWED_MESSAGES)
        if frontend['version'] in WEIGHT_VERSIONS:
            expected[242] = 10673
        if frontend['version'] in ('0.0.11', '0.0.12'):
            expected[243] = 10677
        if frontend['version'] == '0.0.12':
            expected.update({244: 10692, 245: 10696})
        assert {int(key): value for key, value in reviewed.items()} == expected, 'Review the latest human responses before this delivery'


def require_operations_publication(frontend):
    assert frontend['version'] in REVISED_OPERATIONS_VERSIONS, 'T236 message 10650 requires Harvest .9 or later before publication'


def validate_operations_review(frontend, environment, stage_name, proof, review):
    validate_operations_copy(frontend, environment, stage_name, proof)
    assert review['reviewed'] is True
    assert review['web_commit'] == frontend['commit']
    assert review['backend_commit'] == proof['commit']
    assert review['backend_sha256'] == proof['release_sha256']
    assert review['database'] == proof['database']
    checks = OPERATIONS_V9_REVIEW_CHECKS if frontend['version'] in REVISED_OPERATIONS_VERSIONS else OPERATIONS_REVIEW_CHECKS
    if frontend['version'] in WEIGHT_VERSIONS:
        checks += STANDARD_WEIGHT_REVIEW_CHECKS
    if frontend['version'] in ('0.0.11', '0.0.12'):
        checks += ('capture_without_tarja', 'worker_tarja_association_off')
    if frontend['version'] == '0.0.12':
        checks += ('ot_native_fields', 'pass_required', 'ot_work_hours', 'day_allocation', 'native_cost_hours')
    assert all(review[key] is True for key in checks), 'Incomplete crew/lifecycle review'
    if frontend['version'] in REVISED_OPERATIONS_VERSIONS:
        validate_reviewed_messages(frontend, review['reviewed_messages'])


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
        'ot_send_confirmation', 'unconfirmed_delivery_blocks_close'))
    if frontend['version'] in REVISED_OPERATIONS_VERSIONS:
        assert all(operations[key] is True for key in (
            'order_approver_selection', 'native_approval', 'erp_state_approved',
            'ot_reopen_before_send', 'sent_ot_cannot_reopen', 'send_flushes_pending_deliveries',
            'send_retry_idempotency', 'pending_send_atomic', 'send_received_manifest'))
    else:
        assert operations['erp_state_preserved'] is True
    assert all(crew[key] is True for key in (
        'worker_enrollment', 'crew_attendance', 'attendance_home_total',
        'native_members_preserved', 'enrollment_idempotency', 'attendance_idempotency',
        'changed_hours_rejected', 'wrong_date_rejected'))
    if frontend['version'] in REVISED_OPERATIONS_VERSIONS:
        assert crew['harvest_attendance_cosecha_only'] is True
    if frontend['version'] in WEIGHT_VERSIONS:
        assert operations['native_standard_weight'] is True and operations['native_manual_hundredths'] is True
    if frontend['version'] in ('0.0.11', '0.0.12'):
        assert operations['native_capture_without_tarja'] is True
    if frontend['version'] == '0.0.12':
        assert all(operations[key] is True for key in ('ot_native_fields', 'pass_required',
            'ot_work_hours', 'day_allocation', 'native_cost_hours'))


def require_copy_sync_certificate(frontend, environment, stage_name, proof):
    if frontend['version'] in OPERATIONS_VERSIONS:
        validate_operations_copy(frontend, environment, stage_name, proof)
    else:
        assert frontend['version'] == '0.0.7', 'Copy writes require a certified Harvest copy'
        validate_static_copy(frontend, environment, stage_name, proof)


def is_copy_sync_request(enabled, method, path, origin, port, version='0.0.7'):
    paths = OPERATIONS_WRITE_PATHS if version in OPERATIONS_VERSIONS else ('/api/harvest/sync',)
    return (enabled is True and method == 'POST' and path in paths
            and origin == 'http://127.0.0.1:' + str(port))
