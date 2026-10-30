"""Consume a sealed, actually observed native visibility contract; no oracle.

No database connection, role grant, country inference, ID exception or writer.
The coordinator first captures the real source with observer35b9b94d, then
passes that private file's SHA to the target probe. JSON alone grants nothing.
"""
import hashlib
import importlib
import json
from pathlib import Path
import re


SOURCE_OBSERVER_HASHES = {
    'b48f3310adde9899020f6b77d3207a0be73f35cb36e0affb27c9bd6e2fa9f5e1',  # Git LF
    '97f70446aa35138a3e4742de64e0f1669fc5531890b409e18d2d34b4125b3889',  # same CRLF
}
POLICY_TABLES = {'ir_model_access', 'ir_rule', 'rule_group_rel', 'ir_model_fields_group_rel',
    'res_groups', 'res_groups_users_rel', 'res_groups_implied_rel', 'res_company_users_rel'}


class VisibilityBlocked(ValueError):
    """Technical codes only, never payloads or record labels."""


def need(value, code):
    if not value:
        raise VisibilityBlocked('original-source-visibility-' + code)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def observer():
    module = importlib.import_module('probe_original_master_visibility')
    need(sha(Path(module.__file__).read_bytes()) in SOURCE_OBSERVER_HASHES,
        'target-observer-source-does-not-match-approved-git35b9')
    return module


def ids(values):
    return (isinstance(values, list) and all(type(value) is int and value > 0 for value in values)
        and values == sorted(set(values)))


def validate_source(proof, capsule, *, target_database, original_model_id, original_report_ids):
    """Validate sealed source facts; never manufacture source allowed IDs."""
    source = observer()
    need(proof.get('schema') == 1 and proof.get('profile') == 'source-native-original-master-id-visibility'
        and proof.get('database') == target_database.replace('_HANDOVER_', '_REFERENCE_')
        and re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+', target_database),
        'exact-fresh-reference-and-target-pair-required')
    need(proof.get('probe_sha256') in SOURCE_OBSERVER_HASHES
        and proof.get('capsule_sha256') == source.CAPSULE_SHA256, 'source-observer-or-capsule-pin-differs')
    need(proof.get('transaction') == {'read_only': True, 'odoo_cursor_readonly': True,
        'isolation': 'repeatable read', 'local_primary': True}, 'actual-source-readonly-cursor-not-proven')
    engine = proof.get('engine', {})
    need(engine.get('installed') == 381 and engine.get('enterprise') == 140
        and engine.get('oca_installed') is False and engine.get('payslip_model_id') == original_model_id
        and engine.get('report_rows') == [[value, 'hr.payslip'] for value in sorted(original_report_ids)]
        and re.fullmatch('[a-f0-9]{64}', engine.get('module_metadata_sha256', ''))
        and any(name.startswith('odoo.addons.hr_payroll.') for name in engine.get('mro', []))
        and not any(name.startswith('odoo.addons.payroll.') for name in engine.get('mro', [])),
        'original-native-engine-model-report-contract')
    actor = proof.get('actor', {})
    need(type(actor.get('uid')) is int and actor['uid'] > 1
        and ids(actor.get('allowed_company_ids')) and actor['allowed_company_ids']
        and ids(actor.get('original_company_memberships'))
        and set(actor['allowed_company_ids']) <= set(actor['original_company_memberships'])
        and type(actor.get('active_company_id')) is int and actor['active_company_id'] in actor['allowed_company_ids']
        and actor.get('superuser') is False and actor.get('system_group_member') is False
        and actor.get('original_native_payroll_manager') is True
        and actor.get('users_created') is False and actor.get('permissions_granted') is False,
        'existing-normal-native-manager-and-exact-context-required')
    need(proof.get('normal_actor_source_visibility_proven') is True
        and proof.get('original_projection_exact_after') is True and proof.get('active_test') is False
        and proof.get('master_orm_fields_read') == ['id'], 'actual-source-id-read-observation-required')
    for flag in ('source_model_code_overridden', 'source_country_domain_evaluated_locally',
        'historical_payroll_read', 'salary_rules_evaluated', 'salary_amounts_read',
        'formula_bodies_read_from_database', 'database_writes', 'financial_certified',
        'identity_conversion', 'all_products_operational', 'deadline_resolved'):
        need(proof.get(flag) is False, 'source-unsafe-or-unproven-flag:' + flag)
    expected = source.expected_projection(capsule)
    need(proof.get('original_sql_projection') == expected and proof.get('original_sql_projection_sha256')
        == sha(source.encode(expected)), 'source-physical-original-projection-differs')
    models = proof.get('models', {})
    need(set(models) == {model for model, columns in source.SPECS.values()}, 'exact-five-source-models-required')
    for table, (model, columns) in source.SPECS.items():
        seen = models[model]
        need(seen.get('capsule_ids') == [row['id'] for row in expected[table]]
            and all(ids(seen.get(key)) for key in ('capsule_ids', 'allowed_ids', 'denied_ids', 'search_ids'))
            and not set(seen['allowed_ids']) & set(seen['denied_ids'])
            and sorted(seen['allowed_ids'] + seen['denied_ids']) == seen['capsule_ids']
            and seen['search_ids'] == seen['allowed_ids']
            and type(seen.get('search_model_access_denied')) is bool
            and (not seen['search_model_access_denied'] or not seen['allowed_ids'])
            and seen.get('read_fields') == ['id'] and seen.get('read_denial_kind') == 'AccessError'
            and seen.get('search_and_per_record_read_agree') is True and seen.get('superuser') is False,
            'source-allowed-denied-partition-invalid:' + model)
    need(proof.get('total_original_masters') == 120
        and proof.get('allowed_master_ids') == sum(len(row['allowed_ids']) for row in models.values())
        and proof.get('denied_master_ids') == sum(len(row['denied_ids']) for row in models.values()),
        'source-visibility-counts-do-not-reconcile')
    # The real projection still needs every original structure and rule. A
    # source denial is not a license to use a privileged projector.
    need(not models['hr.payroll.structure']['denied_ids'] and not models['hr.salary.rule']['denied_ids'],
        'normal-source-actor-cannot-project-every-original-structure-and-rule')
    policy = proof.get('policy_before', {})
    need(set(policy) == POLICY_TABLES and policy == proof.get('policy_after'), 'source-policy-not-exact')
    for row in policy.values():
        need(type(row.get('rows')) is int and row['rows'] >= 0
            and re.fullmatch('[a-f0-9]{64}', row.get('sha256', '')), 'invalid-source-policy-hash')
    counters = proof.get('business_counters_before', {})
    need(len(counters) >= 140 and counters == proof.get('business_counters_after'), 'source-original-counters-not-exact')
    for name, value in counters.items():
        need(re.fullmatch(r'ir_sequence_[0-9]+(_[0-9]+)?', name)
            and isinstance(value, list) and len(value) == 3 and type(value[0]) is int
            and type(value[1]) is int and type(value[2]) is bool, 'source-counter-identity-or-storage-differs')
    return source


def compare_model(model, expected, *, access_error):
    """Every source-hidden ID must raise the real target AccessError too."""
    actual = observer().observe_model(model, expected['capsule_ids'], access_error=access_error)
    need(actual == expected, 'actual-target-normal-search-read-or-denial-parity-differs')
    return actual


def check_policy_and_counters(proof, policy, counters):
    need(policy == proof['policy_before'] == proof['policy_after'], 'target-security-policy-differs-from-original-source')
    originals = proof['business_counters_before']
    need(all(name in counters and counters[name] == value for name, value in originals.items()),
        'target-original-business-counter-differs-from-source')
    return {'security_tables_exact': len(policy), 'original_business_counters_exact': len(originals),
        'new_target_counter_names': sorted(set(counters) - set(originals)),
        'original_policy_relaxed': False, 'new_grants_authorized': False}
