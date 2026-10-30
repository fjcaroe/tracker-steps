"""Verify private bootstrap evidence offline using only trusted checkout tools.

Artifact Python is hashed as data, never imported or executed. External XML-ID
definitions are server-attested metadata, not a replay of dependency bodies.
Twelve cold tests remain distinct from the accepted 460 normal-profile tests.
"""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

import build_original_bootstrap as builder
import hr_consumer_metadata
import payroll_configuration_adoption_preflight as preflight
import payroll_original_security_admission as security
import audit_payroll_input_storage as input_storage


OWN_MODULES = (
    'step_payroll_contracts', 'step_payroll_oca_api', 'step_payroll_enterprise_reference',
    'step_simpledigital_oca_base', 'step_simpledigital_oca_security',
    'step_hr_contract_lifecycle', 'step_hr_contract_lifecycle_simpledigital',
    'step_payroll_engine_transition', 'steps_hr_payroll_correction', 'step_payroll_batch_period',
    'step_accounting_multicurrency_core', 'step_account_balance_analytic', 'step_bank_export_core',
    'step_account_treasury_batch', 'step_bank_security', 'step_accounting_multicurrency',
    'step_l10n_cl_edi_core', 'step_l10n_cl_caf_custody_core', 'step_l10n_cl_caf_storage',
    'step_l10n_cl_caf_native_reference', 'step_batch_payment_grouping', 'step_batch_payment_core',
)
TOOLS = ('build_original_bootstrap.py', 'build_simpledigital_candidate.py', 'simpledigital_runtime_source.json',
    'validate_original_bootstrap.py', 'probe_original_bootstrap.py', 'validate_payroll_api.py',
    'hr_consumer_metadata.py', 'hr_consumers_candidate.py', 'accelerated_acceptance.py', 'finance_frontier_contract.py',
    'offline_process.py', 'validate_agriculture_core.py', 'payroll_configuration_adoption_preflight.py',
    'payroll_original_security_admission.py', 'verify_native_payroll_configuration.py',
    'prepare_payroll_configuration_storage.py', 'audit_payroll_input_storage.py', 'audit_payroll_input_storage_test.py',
    'audit_simpledigital_seed_graph.py')
EXECUTED_TOOLS = ('build_original_bootstrap.py', 'build_simpledigital_candidate.py', 'simpledigital_runtime_source.json',
    'audit_simpledigital_seed_graph.py', 'validate_original_bootstrap.py', 'probe_original_bootstrap.py',
    'validate_payroll_api.py', 'offline_process.py', 'hr_consumer_metadata.py')
RESULT_PATTERN = re.compile(r'(\d+) failed, (\d+) error\(s\) of (\d+) tests')


class EvidenceError(ValueError):
    pass


def require(value, message):
    if not value:
        raise EvidenceError(message)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def safe_path(root, relative):
    name = str(relative).replace('\\', '/')
    value = PurePosixPath(name)
    require(not value.is_absolute() and '..' not in value.parts and ':' not in name, 'unsafe evidence path')
    target = root / name
    require(target.resolve().is_relative_to(root.resolve()), 'evidence path escapes its root')
    require(not target.is_symlink() and not any(parent.is_symlink() for parent in target.parents if parent != root.parent), 'evidence symlink rejected')
    return target


def read(root, relative):
    return json.loads(safe_path(root, relative).read_text(encoding='utf-8-sig'))


def git_sources(repo):
    paths = list(OWN_MODULES) + ['tools/community/' + name for name in TOOLS]
    data = subprocess.check_output(['git', '-C', str(repo), '-c', 'core.autocrlf=true', '-c', 'core.eol=crlf',
        'archive', '--format=tar', 'HEAD', *paths])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        return {item.name: archive.extractfile(item).read() for item in archive.getmembers() if item.isfile()}


def tool_hash(value, name, source):
    path = 'tools/community/' + name
    # Only Git export EOL policy can differ from Linux execution bytes.
    require(value in {sha(source[path]), sha(source[path].replace(b'\r\n', b'\n'))}, 'tool differs from Git: ' + name)


def test_result(value, expected):
    rows = [RESULT_PATTERN.search(line) for line in value]
    rows = [tuple(map(int, row.groups())) for row in rows if row]
    require(rows and all(row == (0, 0, expected) for row in rows), 'wrong test result or test count')


def no_flags(value, names):
    require(all(value.get(name) is False for name in names), 'evidence claims unsupported conversion or writes')


def addon_snapshot(root, folder):
    base = safe_path(root, folder)
    if (base / builder.MODULE).is_dir():
        base /= builder.MODULE
    result = {}
    for path in base.rglob('*'):
        if path.is_file():
            relative = path.relative_to(root)
            require(safe_path(root, relative) == path, 'unsafe provider snapshot')
            result[path.relative_to(base).as_posix()] = path.read_bytes()
    return result


def verify_packets(root, source):
    packets = [read(root, mode + '/source-files.json') for mode in ('community', 'cerro-reference')]
    require(packets[0] == packets[1] and len(packets[0]) == 355, 'different or incomplete source packets')
    baseline = read(root, 'baseline/source-files.json')
    require(len(baseline) == 358, 'normal accepted baseline packet is incomplete')
    own = {name: value for name, value in packets[0].items() if not name.startswith(builder.MODULE + '/')}
    old = {name: value for name, value in baseline.items() if not name.startswith(builder.MODULE + '/')}
    require(own == old and {name.split('/')[0] for name in own} == set(OWN_MODULES), 'owned modules changed from Inputs C')
    expected = {name: sha(value) for name, value in source.items() if name.split('/')[0] in OWN_MODULES}
    require(own == expected, 'owned addon packet differs from exact Git export')
    return packets[0], baseline


def verify_provider(root, source, packet, baseline):
    original = addon_snapshot(root, 'original-provider')
    normal = addon_snapshot(root, 'normal-provider')
    cold = addon_snapshot(root, 'provider')
    require((len(original), len(normal), len(cold)) == (52, 52, 49), 'wrong provider snapshot file counts')
    pin = json.loads(source['tools/community/simpledigital_runtime_source.json'].decode('utf-8-sig'))
    report = read(root, builder.REPORT)
    definitions = read(root, 'dependency-definitions.json')
    require(definitions['server_metadata_only'] and definitions['bodies_replayed_offline'] is False, 'dependency definitions are not a metadata-only attestation')
    require(definitions['dependencies'] == report['dependencies'], 'dependency attestation differs from the build')
    require(definitions['definitions_sha256'] == builder.digest(definitions['definitions']), 'dependency definition digest mismatch')
    builder.verify_snapshots(original, normal, cold, report, definitions['definitions'], pin)
    tool_hash(report['builder_sha256'], 'build_original_bootstrap.py', source)
    tool_hash(report['normal_builder_sha256'], 'build_simpledigital_candidate.py', source)
    for module, data in report['dependencies'].items():
        require(data['license'] in ('LGPL-3', 'AGPL-3'), 'nonfree dependency attested')
        if module in OWN_MODULES:
            expected = {name.split('/', 1)[1]: sha(value) for name, value in source.items() if name.startswith(module + '/')}
            require(data['files'] == expected, 'owned dependency snapshot differs from Git')
    for files, listing in ((cold, packet), (normal, baseline)):
        require({builder.MODULE + '/' + name: sha(value) for name, value in files.items()}
            == {name: value for name, value in listing.items() if name.startswith(builder.MODULE + '/')}, 'provider packet mismatch')
    closure = report['closure']
    require(set(closure['omitted_files']) == set(builder.OMIT) and len(builder.OMIT) == 3, 'seed omission policy drift')
    require(not closure['retained_salary_records'] and not closure['operational_payroll_package'], 'bootstrap claims operational payroll')
    require(closure['deferred_seed_assignment']['must_adopt_before_chile_processing'], 'unpaid policy gate missing')
    require(closure['deferred_movement_catalogue']['must_adopt_before_movement_processing'], 'movement catalogue gate missing')
    return report


def verify_hr_derivation(root, source):
    proof = read(root, 'community/hr-consumers-derivation.json')
    tool_hash(proof['builder_sha256'], 'hr_consumers_candidate.py', source)
    require(proof['community_candidate'] and not proof['identity_conversion_accepted'], 'HR derivation claim invalid')
    expected = {}
    dependency_map = {'hr_payroll': 'step_simpledigital_oca_security', 'hr_work_entry_contract_enterprise': 'hr_work_entry_contract'}
    for module, data in proof['modules'].items():
        for relative, pair in data['files'].items():
            name = module + '/' + relative
            blob = source[name]
            require(sha(blob) == pair['source'], 'HR original source mismatch')
            if relative == '__manifest__.py':
                spec = ast.literal_eval(blob.decode('utf-8-sig'))
                spec['depends'] = list(dict.fromkeys(dependency_map.get(name, name) for name in spec['depends']))
                blob = (repr(spec) + '\n').encode()
            elif name.endswith(('.xml', '.csv')):
                text = blob.decode('utf-8-sig')
                for before, after in proof['xmlid_map'].items():
                    text = text.replace(before, after)
                blob = text.encode()
            require(sha(blob) == pair['candidate'], 'HR derived source mismatch')
            expected[name] = sha(blob)
    require(read(root, 'community/consumer-source-files.json') == expected, 'HR CE overlay differs')
    native = read(root, 'cerro-reference/consumer-source-files.json')
    require(set(native) == set(expected) and all(value == sha(source[name]) for name, value in native.items()), 'HR native source differs')


def verify_native(root, source, passed):
    test_result(passed['test_results'], 294)
    require(passed['expected_test_count'] == 294 and passed['counts'] == {'installed': 391, 'enterprise': 140}, 'native graph or count mismatch')
    no_flags(passed, ('writes_to_source', 'historical_conversion', 'simpledigital_certified'))
    tool_hash(passed['validator_sha256'], 'validate_payroll_api.py', source)
    tool_hash(passed['identity_snapshot_tool_sha256'], 'validate_agriculture_core.py', source)
    tool_hash(passed['offline_runner_sha256'], 'offline_process.py', source)
    for name, value in passed['accelerated_tools_sha256'].items():
        tool_hash(value, name, source)
    require(passed['external_network_disabled'] and passed['loopback_http_only'] and passed['postgres_unix_socket'], 'native isolation evidence missing')
    before = read(root, 'cerro-reference/business-before.json')
    require(len(before) == 1061 and before == read(root, 'cerro-reference/business-after.json'), 'original business/counters changed')
    require(read(root, 'cerro-reference/history-before.json') == read(root, 'cerro-reference/history-after.json'), 'original payroll history changed')
    original, current = read(root, 'cerro-reference/identity-before.json'), read(root, 'cerro-reference/identity-after.json')
    require(passed['original_xmlid_noupdate_captured'] and all('noupdate' in row for row in original['original_xmlids']), 'original XML-ID noupdate custody missing')
    audit = hr_consumer_metadata.verify(original, current)
    audit['source']['sha256'] = sha(source[audit['source']['path']])
    require(audit == read(root, 'cerro-reference/hr-metadata-proof.json'), 'HR exact message policy differs')
    for name, rows in original.items():
        if name == 'ir_model_fields':
            continue
        after = current[name]
        if rows and 'id' in rows[0]:
            indexed = {row['id']: row for row in after}
            require(len(indexed) == len(after) and all(indexed.get(row['id']) == row for row in rows), 'original metadata identity changed: ' + name)
        else:
            require(all(row in after for row in rows), 'original metadata relation changed: ' + name)
    return {'business_contracts': len(before), 'history_exact': True, 'identity_rows': {name: len(rows) for name, rows in original.items()}}


def verify_preflight(root, source, cold, native):
    before, after = read(root, 'configuration-preflight/before.json'), read(root, 'configuration-preflight/after.json')
    comparison = preflight.compare_reports(before, after)
    require(comparison['read_only_evidence_unchanged'] and after['read_only_comparison'] == comparison, 'configuration preflight changed')
    for report in (before, after):
        tool_hash(report['tool_sha256'], 'payroll_configuration_adoption_preflight.py', source)
        require(report['target_database'] == cold['database'], 'preflight targets another database')
        assess = report['assessment']
        require(assess['source_master_count'] == 120 and assess['source_xmlid_count'] == 91, 'original configuration count differs')
        counts = {'hr_payroll_structure': 4, 'hr_payroll_structure_type': 5, 'hr_payslip_input_type': 6,
            'hr_salary_rule': 71, 'hr_salary_rule_category': 34}
        require(all(len(report['source_metadata']['rows:' + table]) == count for table, count in counts.items()), 'original metadata row counts differ')
        require(all(len(report['target_metadata']['rows:' + table]) == (4 if table == 'hr_payroll_structure_type' else 0)
            for table in counts), 'cold preflight contains adopted salary masters')
        require(assess['source_capsule_matches_live_configuration'] and assess['source_capsule_field_metadata_matches']
            and assess['target_has_zero_enterprise'] and assess['reference_target_only'], 'source/preflight custody failed')
        no_flags(assess, ('adoption_ready', 'import_authorized', 'permissions_expanded', 'orm_loaded', 'rules_evaluated', 'salary_formulas_exposed', 'historical_payroll_read', 'record_rule_equivalence_certified'))
    security_proof = read(root, 'configuration-preflight/security-admission.json')
    tool_hash(security_proof['tool_sha256'], 'payroll_original_security_admission.py', source)
    require(security_proof['target_database'] == cold['database'] and security_proof['capsule_sha256'] == after['capsule_sha256'], 'security provenance mismatch')
    plan = security.preservation_plan(security_proof['source'], security_proof['target'])
    require(plan == security_proof['plan'] and plan['blockers'] and not plan['metadata_preservation_admissible'], 'security blockers were suppressed')
    no_flags(plan, ('group_memberships_changed', 'manager_assigned', 'field_groups_changed', 'database_writes', 'import_authorized', 'dependency_change_authorized', 'record_rule_equivalence_certified', 'engine_converted'))
    require(plan['new_acl_grants'] == [], 'additional ACL grants admitted')
    provenance = read(root, 'configuration-preflight/native-source.json')
    require(provenance['native_database'] == native['database'] and provenance['capsule_sha256'] == after['capsule_sha256'], 'native configuration provenance mismatch')
    tool_hash(provenance['generator_sha256'], 'verify_native_payroll_configuration.py', source)
    require(provenance['native_metadata_before'] == provenance['native_metadata_after'] and provenance['two_readonly_snapshots_equal'], 'native configuration changed')
    require(provenance['source_master_count'] == 120 and provenance['all_six_table_hashes_and_counts_equal'], 'native original master custody failed')
    require(all(provenance['native_metadata_before']['source_hash:' + table] == after['source_metadata']['source_hash:' + table]
        for table in preflight.TABLES), 'native original master hashes differ from the source preflight')
    no_flags(provenance, ('orm_loaded', 'rules_evaluated', 'historical_payroll_read', 'salary_formulas_exposed', 'adoption_authorized', 'engine_converted', 'financial_certified'))
    classification = read(root, 'configuration-preflight/native-xmlid-classification.json')
    require(classification['identity_before_sha256'] == sha(safe_path(root, 'cerro-reference/identity-before.json').read_bytes())
        and classification['identity_after_sha256'] == sha(safe_path(root, 'cerro-reference/identity-after.json').read_bytes())
        and classification['native_provenance_sha256'] == sha(safe_path(root, 'configuration-preflight/native-source.json').read_bytes()), 'native alias custody mismatch')
    require(classification['origin_xmlids_present_before_upgrade'] == 88 and classification['reference_aliases_absent_before_upgrade'] == 3
        and classification['unexpected_drift'] == [] and classification['all_original_xmlids_and_noupdate_preserved'], 'native original/reference aliases conflated')
    origin_aliases = classification['origin_alias_records']
    reference_aliases = classification['reference_alias_records']
    require(len(origin_aliases) == 88 and len(reference_aliases) == 3, 'native alias classification counts differ')
    require(all(row['capsule'] == row['native_before'] == row['native_after'] and not row['before_vs_capsule_differences']
        and not row['capsule_vs_native_after_differences'] for row in origin_aliases), 'original alias identity changed')
    require(all({key: value for key, value in row['capsule'].items() if key != 'id'}
        == {key: value for key, value in row['native_after'].items() if key != 'id'} for row in reference_aliases), 'reference aliases changed their real bindings')
    require(classification['adapter_source']['sha256'] in {sha(source['step_simpledigital_oca_security/hooks.py']),
        sha(source['step_simpledigital_oca_security/hooks.py'].replace(b'\r\n', b'\n'))}, 'native adapter source differs')
    storage = read(root, 'configuration-storage/community-current-contract.json')
    require(storage['read_only'] and not storage['orm_loaded'], 'current configuration storage is not readonly evidence')
    require(storage['versions']['step_payroll_oca_api'] == ast.literal_eval(source['step_payroll_oca_api/__manifest__.py'].decode('utf-8-sig'))['version'], 'configuration storage API version differs')
    original_storage = read(root, 'configuration-storage/community-contract.json')
    require(all(storage[key] == original_storage[key] for key in ('fields', 'relation')), 'configuration relation storage contract changed')
    preparation = read(root, 'configuration-storage/passed.json')
    require(read(root, 'configuration-storage/original-before.json') == read(root, 'configuration-storage/original-after.json'), 'previous SQL preparation changed original rows')
    require(preparation['memberships'] == 71 and preparation['company_or_parent_values_assigned'] == 0
        and preparation['backup_decoded'] and preparation['idempotence_verified'] and preparation['original_metadata_preserved'], 'previous SQL preparation was not preserved')
    no_flags(preparation, ('orm_loaded', 'engine_converted', 'financial_certified', 'writes_to_source', 'paid_payroll_recomputed'))
    tool_hash(preparation['tool_sha256'], 'prepare_payroll_configuration_storage.py', source)
    return {'source_masters': 120, 'source_xmlids': 91, 'original_aliases': 88, 'reference_aliases': 3,
        'remaining_field_gaps': len(after['assessment']['field_differences']),
        'remaining_physical_gaps': len(after['assessment']['column_differences']),
        'security_blockers': len(plan['blockers']), 'adopted': False}


def verify_input_storage(root, source):
    receipt = read(root, 'input-storage/receipt.json')
    for name, value in receipt['files_sha256'].items():
        require(sha(safe_path(root, 'input-storage/' + name).read_bytes()) == value, 'input storage custody mismatch')
    for name in ('audit_payroll_input_storage.py', 'audit_payroll_input_storage_test.py'):
        body = safe_path(root, 'input-storage/' + name).read_bytes()
        require(body.replace(b'\r\n', b'\n') == source['tools/community/' + name].replace(b'\r\n', b'\n'), 'input storage tool differs from Git')
    tool = sha(safe_path(root, 'input-storage/audit_payroll_input_storage.py').read_bytes())
    reports = {}
    for mode in ('community', 'native', 'sys'):
        report = read(root, 'input-storage/' + mode + '.json')
        require(report['tool_sha256'] == tool and report['read_only'] and report['metadata_before'] == report['metadata_after'], 'input storage snapshot changed')
        no_flags(report, ('orm_loaded', 'salary_rows_read', 'salary_amounts_read', 'database_writes', 'rules_evaluated', 'conversion_authorized', 'source_bodies_exported'))
        reports[mode] = report
    plan = read(root, 'input-storage/plan.json')
    require(plan['tool_sha256'] == tool and plan['catalog_only'], 'input storage classification provenance mismatch')
    for mode in reports:
        require(plan['reports_sha256'][mode] == sha(safe_path(root, 'input-storage/' + mode + '.json').read_bytes()), 'input storage report hash differs')
    require(plan['native_to_community'] == input_storage.classify(reports['native']['metadata_before'], reports['community']['metadata_before'])
        and plan['sys_to_community'] == input_storage.classify(reports['sys']['metadata_before'], reports['community']['metadata_before']), 'input storage classification differs')
    no_flags(plan, ('conversion_authorized', 'rows_read', 'customer_precision_assessed'))
    return {'catalog_only': True, 'reference_profiles': ['Inputs C Community', 'Inputs C native', 'SyS'],
        'precision_preservation_certified': False, 'conversion_authorized': False}


def verify(evidence, *, repo=None):
    root = Path(evidence).resolve()
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parents[2]
    source = git_sources(repo)
    executed = safe_path(root, 'executed-tools')
    require(executed.is_dir() and {path.name for path in executed.iterdir()} == set(EXECUTED_TOOLS), 'executed helper snapshots missing or unexpected')
    for path in executed.iterdir():
        require(path.is_file() and path.name in TOOLS, 'unexpected executed helper')
        expected = source['tools/community/' + path.name]
        require(path.read_bytes().replace(b'\r\n', b'\n') == expected.replace(b'\r\n', b'\n'), 'executed helper differs from Git')
    packet, baseline = verify_packets(root, source)
    provider = verify_provider(root, source, packet, baseline)
    verify_hr_derivation(root, source)
    cold, native = read(root, 'community/passed.json'), read(root, 'cerro-reference/passed.json')
    require(cold['counts'] == {'installed': 94, 'enterprise': 0} and cold['demo_installed_modules'] == 0
        and cold['without_demo'] == 'all' and cold['expected_test_count'] == 12, 'cold module/demo/test graph differs')
    test_result(cold['test_results'], 12)
    no_flags(cold, ('operational_package', 'historical_conversion', 'original_masters_imported', 'simpledigital_certified',
        'financial_certified', 'writes_to_source', 'deferred_unpaid_membership_adopted'))
    require(cold['profile'] == provider['profile'] and cold['fixtures_rolled_back'] and cold['registry_forms_defaults_acl_verified']
        and cold['external_network_disabled'] and cold['postgres_unix_socket'], 'cold execution provenance incomplete')
    for mode, passed in (('community', cold), ('cerro-reference', native)):
        require(passed['source_files_sha256'] == sha(safe_path(root, mode + '/source-files.json').read_bytes())
            and passed['package_files'] == 355, 'passed receipt references another packet')
        text = safe_path(root, mode + '/tests.log').read_text(errors='replace')
        require(not re.search(r' (ERROR|CRITICAL) ', text), 'test log contains an error')
        test_result([line for line in text.splitlines() if 'tests.result' in line], 12 if mode == 'community' else 294)
    for key, name in (('runner_sha256', 'validate_original_bootstrap.py'), ('probe_sha256', 'probe_original_bootstrap.py')):
        tool_hash(cold[key], name, source)
    require(cold['bootstrap_derivation_sha256'] == sha(safe_path(root, builder.REPORT).read_bytes()), 'cold derivation receipt differs')
    probe = read(root, 'community/registry-before.json')
    require(probe == read(root, 'community/registry-after.json'), 'cold registry probe changed')
    require(probe['database'] == cold['database'] and probe['real_oca_engine'] and probe['normal_actor']
        and probe['actors_rolled_back'] and probe['official_structure_types'] == 4, 'cold real-engine/actor/type proof incomplete')
    require(probe['salary_counts_before'] == probe['salary_counts_after'] and not any(probe['salary_counts_before'].values()), 'cold salary data or history leaked')
    require(probe['officer_batch_read_denied'] and probe['internal_salary_rule_write_denied'] and probe['visible_payroll_root'], 'cold original ACL changed')
    no_flags(probe, ('deferred_unpaid_membership_adopted', 'original_masters_imported', 'operational_package',
        'historical_conversion', 'financial_certified', 'form_probe_created_payslips', 'form_probe_created_contracts'))
    baseline_passed = read(root, 'baseline/passed.json')
    test_result(baseline_passed['test_results'], 460)
    require(baseline_passed['expected_test_count'] == 460 and baseline_passed['source_files_sha256']
        == sha(safe_path(root, 'baseline/source-files.json').read_bytes()), 'accepted normal baseline provenance differs')
    preservation = verify_native(root, source, native)
    gates = verify_preflight(root, source, cold, native)
    inputs = verify_input_storage(root, source)
    return {'schema': 1, 'exact_packet_matches_git': True, 'owned_modules_unchanged_from_inputs_C': 22,
        'package_files': 355, 'provider_files': {'original': 52, 'normal': 52, 'cold': 49},
        'cold': {'tests': 12, 'installed': 94, 'enterprise': 0, 'demo': 0, 'salary_rows': 0},
        'native_reference': {'tests': 294, 'installed': 391, 'enterprise': 140, **preservation},
        'prior_normal_profile': {'tests': 460, 'distinct_from_cold_tests': True},
        'dependency_definitions': {'server_attested': True, 'dependency_bodies_replayed_offline': False},
        'configuration': gates, 'input_storage': inputs,
        'original_masters_imported': False, 'operational_package': False, 'historical_conversion': False,
        'financial_certified': False, 'simpledigital_certified': False, 'deadline_resolved': False,
        'artifact_code_executed': False, 'verifier_sha256': sha(Path(__file__).read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.evidence)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print('ORIGINAL_BOOTSTRAP_EVIDENCE_VERIFIED: cold12 / native294; original adoption remains pending')


if __name__ == '__main__':
    main()
