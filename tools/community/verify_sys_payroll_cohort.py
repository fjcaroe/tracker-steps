"""Offline replay of sealed SyS cohort A using trusted Git code only.

No SQL, ORM, artifact imports, formula evaluation or financial certification.
The original capture and the pre-existing positive/zero references are pinned;
contract candidate entries are never called original payslip work entries.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess

import capture_sys_payroll_cohort as capture


CAPTURE_SHA256 = '488437ac9e936279bf891c6a9c6c7ba053360fb098dd95c786f7921e50ccce77'
SOURCE_HELPER_SHA256 = 'cde90857c983e12124ee185abae7b61513ca07bd74b7a84dc6c0d4530c92f558'
POSITIVE_REFERENCE_SHA256 = '495b673c4160684aa26a0a5f9ad4d814f8f7791f300dc0d12d7a9856df407e41'
ZERO_REFERENCE_SHA256 = '05a9cdc76af38baaeda0f481e499156bfa8adc2bff5f48e4d74ce05c3e41b39e'
BASIC_COMPONENT_REFERENCE_SHA256 = '573e15b65076b745c24cb8048329654ae774d7ca827062daf9b637453429ae6c'
require, sha = capture.require, capture.sha


def sealed_json(path, expected):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'regular-private-custody-file-required')
    body = path.read_bytes()
    require(sha(body) == expected, 'private-evidence-seal-differs')
    return json.loads(body), body


def unique(rows, key, code):
    values = {row[key] for row in rows}
    require(len(values) == len(rows) and all(type(value) is int and value > 0 for value in values), code)
    return values


def shape_and_bindings(payload):
    expected = set(capture.CONFIG_TABLES + capture.CONFIG_RELATIONS + capture.PAYROLL_TABLES)
    require(set(payload['schema']) == set(payload['snapshots']) == expected and len(expected) == 12,
        'exact-twelve-table-snapshot-required')
    for name in expected:
        schema, snapshot = payload['schema'][name], payload['snapshots'][name]
        require(schema and len({row[0] for row in schema}) == len(schema)
            and all(len(row) == 3 and isinstance(row[0], str) and isinstance(row[1], str) and type(row[2]) is bool for row in schema),
            'complete-physical-column-metadata-required')
        require(type(snapshot['rows']) is int and snapshot['rows'] >= 0
            and len(snapshot['sha256']) == 64 and all(c in '0123456789abcdef' for c in snapshot['sha256']),
            'table-row-hash-contract-required')
    header_ids = unique(payload['headers'], 'id', 'duplicate-or-invalid-header-id')
    headers = {row['id']: row for row in payload['headers']}
    contracts = {row['contract_id'] for row in headers.values()}
    require(all(type(value) is int and value > 0 for value in contracts), 'header-contract-binding-incomplete')
    require(unique(payload['contract_provenance'], 'id', 'contract-provenance-identity-invalid') == contracts,
        'actual-selected-contract-provenance-differs')
    for name, parent in (('lines', 'slip_id'), ('worked_days', 'payslip_id'), ('inputs', 'payslip_id')):
        unique(payload[name], 'id', 'duplicate-or-invalid-child-id')
        require(all(row[parent] in header_ids for row in payload[name]), 'child-header-binding-differs')
    unique(payload['work_entries'], 'id', 'duplicate-or-invalid-work-entry-id')
    require(all(row['contract_id'] in contracts for row in payload['work_entries']), 'candidate-work-entry-contract-binding-differs')
    rule_ids = unique(payload['rules'], 'id', 'duplicate-or-invalid-current-rule-id')
    require(set(payload['configuration_keys']) == set(capture.MODELS.values()), 'configuration-identity-inventory-incomplete')
    require(set(payload['configuration_keys']['hr.salary.rule']) == rule_ids,
        'current-rule-identity-inventory-differs')
    for table, model in capture.MODELS.items():
        values = payload['configuration_keys'][model]
        require(len(values) == len(set(values)) == payload['snapshots'][table]['rows'], 'configuration-key-count-differs')
    unresolved = []
    for row in payload['lines']:
        if row['salary_rule_id'] not in rule_ids:
            unresolved.append({'model': 'hr.payslip.line', 'id': row['id'], 'code': 'CURRENT_RULE_ENDPOINT_MISSING'})
    for name in ('inputs', 'worked_days'):
        for row in payload[name]:
            if row['type_id'] is None or row['current_type_code'] is None:
                unresolved.append({'model': name, 'id': row['id'], 'code': 'CURRENT_TYPED_ENDPOINT_MISSING'})
    require(len(payload['headers']) <= payload['snapshots']['hr_payslip']['rows']
        and len(payload['lines']) <= payload['snapshots']['hr_payslip_line']['rows']
        and len(payload['worked_days']) <= payload['snapshots']['hr_payslip_worked_days']['rows']
        and len(payload['inputs']) <= payload['snapshots']['hr_payslip_input']['rows']
        and len(payload['work_entries']) <= payload['snapshots']['hr_work_entry']['rows'], 'captured-subset-exceeds-original-table')
    return {'snapshot_tables': 12, 'headers': len(headers), 'contracts': len(contracts),
        'payroll_children_bind_to_captured_header': True, 'header_contracts_bind_to_actual_contract_rows': True,
        'work_entries_bind_to_selected_contracts': True, 'direct_work_entry_payslip_link_proven': False,
        'work_entries_are_period_or_policy_approved': False, 'foreign_key_constraints_introspected': False,
        'unresolved_endpoints': unresolved}


def reference_overlap(payload, reference):
    case = reference['selected_case']
    header = next((row for row in payload['headers'] if row['id'] == case['id']), None)
    actual = {row['id']: row for row in payload['lines']}
    observations = [row for rows in case['concepts'].values() for row in rows]
    exact_lines = all(row['id'] in actual and all(actual[row['id']][key] == row[key]
        for key in ('id', 'slip_id', 'salary_rule_id', 'code', 'total', 'write_date')) for row in observations)
    exact_lines = exact_lines and {row['id'] for row in payload['lines'] if row['slip_id'] == case['id']
        and row['code'] in ('BASIC', 'GROSS', 'NET')} == {row['id'] for row in observations}
    header_exact = header is not None and all(header[key] == case[key] for key in ('state', 'date_from', 'date_to'))
    if 'structure_id' in case:
        header_exact = header_exact and header['struct_id'] == case['structure_id']
    if case.get('basis'):
        header_exact = header_exact and header['contract_id'] == case['basis']['contract_id']
    days = {row['id']: row for row in payload['worked_days']}
    inputs = {row['id']: row for row in payload['inputs']}
    days_exact = all(row['id'] in days and days[row['id']]['payslip_id'] == case['id']
        and all(days[row['id']][key] == row[key] for key in ('type_id', 'days', 'hours', 'amount'))
        for row in case.get('basis', {}).get('worked_days', []))
    inputs_exact = all(row['id'] in inputs and inputs[row['id']]['payslip_id'] == case['id']
        and all(inputs[row['id']][key] == row[key] for key in ('type_id', 'amount'))
        for row in case.get('basis', {}).get('inputs', []))
    days_exact = days_exact and {row['id'] for row in payload['worked_days'] if row['payslip_id'] == case['id']} == {
        row['id'] for row in case.get('basis', {}).get('worked_days', [])}
    inputs_exact = inputs_exact and {row['id'] for row in payload['inputs'] if row['payslip_id'] == case['id']} == {
        row['id'] for row in case.get('basis', {}).get('inputs', [])}
    ambiguous = []
    for item in reference['ambiguous_concepts']:
        rows = [row for row in payload['lines'] if row['slip_id'] == item['slip_id'] and row['code'] == item['code']]
        ambiguous.append({'present': bool(rows), 'identities_exact': sorted({row['salary_rule_id'] for row in rows}) == item['rule_ids'],
            'line_ids_exact': sorted(row['id'] for row in rows) == sorted(item['line_ids']),
            'zero_line_preserved': any(Decimal(row['total']) == 0 for row in rows)})
    return {'selected_case_present': header is not None, 'selected_header_identity_exact': header_exact,
        'stored_essential_line_identity_text_total_write_date_exact': exact_lines,
        'stored_worked_days_exact': days_exact, 'stored_inputs_exact': inputs_exact,
        'selected_case_has_positive_essential_totals': reference.get('selected_case_has_positive_essential_totals', False),
        'selected_case_has_zero_essential_total': any(Decimal(v) == 0 for v in case['stored_totals'].values()),
        'ambiguous_references': ambiguous, 'financial_certified': False}


def basic_components_overlap(payload, basis, positive_body):
    require(basis['capsule_sha256'] == sha(positive_body) and basis['components_read_only_sql'] is True
        and basis['source_payroll_computed'] is False and basis['financial_certified'] is False,
        'approved-basic-component-provenance-differs')
    expected = basis['expected_components']
    actual = next((row for row in payload['lines'] if row['id'] == expected['id']), None)
    require(actual is not None and actual['slip_id'] == expected['slip_id']
        and actual['salary_rule_id'] == expected['salary_rule_id'] and actual['code'] == expected['code'],
        'approved-basic-original-line-binding-differs')
    return {'raw_components_exact': {field: actual[field] == expected[field] for field in ('amount', 'quantity', 'rate', 'total')},
        'decimal_components_equal': {field: Decimal(actual[field]) == Decimal(expected[field]) for field in ('amount', 'quantity', 'rate', 'total')},
        'source_line_identity_exact': True, 'formula_evaluated': False, 'full_payroll_replay': False}


def verify(cohort_path, capsule_path, positive_path, zero_path, basis_path, registry_path, *, repo):
    # The current imported helper and the trusted HEAD blob must be the exact
    # capture implementation a15517d0 (LF/CRLF is the only text transport change).
    helper = subprocess.check_output(['git', '-C', str(repo), 'show', 'HEAD:tools/community/capture_sys_payroll_cohort.py'])
    require(sha(helper.replace(b'\r\n', b'\n')) == SOURCE_HELPER_SHA256
        and sha(Path(capture.__file__).read_bytes().replace(b'\r\n', b'\n')) == SOURCE_HELPER_SHA256,
        'trusted-original-a155-helper-required')
    proof, _ = sealed_json(cohort_path, CAPTURE_SHA256)
    capsule, _ = sealed_json(capsule_path, capture.CERRO_CAPSULE_SHA256)
    positive, positive_body = sealed_json(positive_path, POSITIVE_REFERENCE_SHA256)
    zero, _ = sealed_json(zero_path, ZERO_REFERENCE_SHA256)
    basis, _ = sealed_json(basis_path, BASIC_COMPONENT_REFERENCE_SHA256)
    require(proof['tool_sha256'] == SOURCE_HELPER_SHA256 and proof['cerro_capsule_sha256'] == capture.CERRO_CAPSULE_SHA256,
        'original-source-or-capsule-binding-differs')
    require(proof['atomic_read_only_transaction'] is True and proof['reference'] == 'sys_user_approved'
        and proof['database'] == 'SyS' and proof['contains_private_financial_data'] is True,
        'approved-atomic-private-reference-required')
    for flag in ('orm_loaded', 'payroll_computed', 'database_writes', 'formula_bodies_exported',
            'direct_employee_identifiers_exported', 'financial_certified', 'master_timeline_certified',
            'full_payroll_replay', 'identity_conversion', 'deadline_resolved'):
        require(proof[flag] is False, 'capture-overclaims-operation-or-certification')
    registry_body = Path(registry_path).read_bytes()
    require(sha(registry_body) == proof['registry_sha256'], 'original-canonical-registry-seal-differs')
    registry = json.loads(registry_body.decode('utf-8-sig'))
    row = registry.get('environments', {}).get('sys', {})
    require(registry.get('instance') == 'odoo-new' and row.get('role') == 'production'
        and row.get('database') == 'SyS' and row.get('config') == '/etc/odoo18-sys.conf',
        'original-canonical-sys-registry-required')
    pin_body = subprocess.check_output(['git', '-C', str(repo), 'show',
        'HEAD:tools/community/simpledigital_runtime_source.json'])
    pin = json.loads(pin_body.decode('utf-8-sig'))
    require(sha(pin_body) == proof['provider_pin_sha256'] and proof['provider_source']['files'] == pin['files']
        and len(pin['files']) == 52 and proof['provider_source']['license'] == pin['license'] == 'AGPL-3'
        and proof['provider_source']['version'] == pin['version'], 'listed-provider-file-pin-differs')
    payload = proof['payload']
    require(proof['sql_sha256'] == sha(capture.sql_capture(payload['metadata']['as_of']).encode()),
        'single-readonly-sql-source-differs')
    issues = capture.validate_payload(payload, proof['provider_source'])
    require(issues == proof['stored_data_issues'], 'stored-anomaly-report-differs')
    bindings = shape_and_bindings(payload)
    matrix = capture.compare_rules(capsule, payload)
    require(len(matrix) == 71 and matrix == proof['cerro_rule_coverage'], 'original71-coverage-replay-differs')
    population = payload['closed_population']
    return {'schema': 1, 'capture_sha256': CAPTURE_SHA256, 'source_helper_sha256': SOURCE_HELPER_SHA256,
        'verifier_sha256': sha(Path(__file__).read_bytes()), 'registry_exact': True, 'listed_provider_files_exact': True,
        'runtime_config_file_rehashed_offline': False,
        'cerro_capsule_sha256': capture.CERRO_CAPSULE_SHA256, 'atomic_read_only_source': True,
        'source_closed_total': population['all_closed'], 'previous_month_closed_cohort': len(payload['headers']),
        'excluded_by_current_month_cutoff': population['all_closed'] - len(payload['headers']),
        'document_reference_D_closed_total': positive['closed_slips'],
        'observed_closed_count_delta_since_D': population['all_closed'] - positive['closed_slips'],
        'creator_or_change_timeline_attributed': False,
        'stored_lines': len(payload['lines']), 'worked_days': len(payload['worked_days']), 'inputs': len(payload['inputs']),
        'work_entries_contract_candidates_only': len(payload['work_entries']), 'bindings': bindings,
        'data_issues_by_code': dict(Counter(row['code'] for row in issues)),
        'source_current_rules': len(payload['rules']), 'cerro_rules': len(matrix),
        'original_xmlid_bindings': sum(row['binding'] == 'same_original_xmlid' for row in matrix),
        'rules_with_stored_coverage': sum(bool(row['stored_line_ids']) for row in matrix),
        'current_comparable_fields_match': sum(row['binding'] == 'same_original_xmlid' and not row['current_differences'] for row in matrix),
        'configuration_differences_by_field': dict(Counter(field for row in matrix for field in row['current_differences'])),
        'blockers_by_code': dict(Counter(code for row in matrix for code in row['blockers'])),
        'positive_D_overlap': reference_overlap(payload, positive), 'zero_F_overlap': reference_overlap(payload, zero),
        'approved_BASIC_components_overlap': basic_components_overlap(payload, basis, positive_body),
        'provider_listed_files': len(proof['provider_source']['files']), 'provider_inventory_exhaustive': False,
        'provider_execution_closure_certified': False,
        'provider_limit': 'Capture pinned the listed 52 files; extra runtime files were not enumerated atomically.',
        'field_and_record_acl_runtime_exercised': False, 'database_accessed_by_replay': False, 'artifact_code_executed': False,
        'formula_evaluated': False, 'financial_certified': False, 'master_timeline_certified': False,
        'original_masters_adopted': False, 'full_payroll_replay': False, 'historical_conversion': False, 'deadline_resolved': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('cohort', 'cerro-capsule', 'positive-reference', 'zero-reference', 'basic-reference', 'registry', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.cohort, args.cerro_capsule, args.positive_reference, args.zero_reference, args.basic_reference, args.registry,
        repo=Path(__file__).resolve().parents[2])
    raw = json.dumps(result, indent=2, sort_keys=True).encode()
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'file': str(args.output), 'sha256': sha(raw), 'tables': result['bindings']['snapshot_tables'],
        'closed_previous_months': result['previous_month_closed_cohort'], 'excluded_current_month': result['excluded_by_current_month_cutoff'],
        'cerro_rules': result['cerro_rules'], 'original_xmlid_bindings': result['original_xmlid_bindings'],
        'financial_certified': False, 'database_accessed': False}))


if __name__ == '__main__':
    main()
