"""Offline custody for the cold NUMERIC-input and explicit-rule-projection block.

Only trusted checkout modules are imported. Artifact Python is inert data.
The 25 cold cases are separate from bootstrap F's 12 and normal Inputs C's 460.
No successful check authorizes original-master adoption or a production cutover.
"""
import argparse
import ast
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
from xml.etree import ElementTree as ET

import build_numeric_input_engine as numeric
import build_original_bootstrap as builder
import build_simpledigital_candidate as normal_builder
import verify_original_bootstrap_evidence as base


require = base.require
sha = base.sha
read = base.read
safe_path = base.safe_path
TOOLS = tuple(dict.fromkeys(base.TOOLS + ('build_numeric_input_engine.py',
    'audit_stock_package_representation.py', 'audit_product_frontier.py', 'collect_original_contracts.py',)))
TEST_CLASSES = (
    ('step_payroll_oca_api/tests/test_saved_inputs.py', 'SavedInputValuesCase', 6),
    ('step_simpledigital_oca_base/tests/test_existing_batch.py', 'ExistingDraftBatchCase', 6),
    ('step_payroll_oca_api/tests/test_original_input_storage.py', 'OriginalInputStorageCase', 6),
    ('step_payroll_oca_api/tests/test_original_rule_projection.py', 'OriginalRuleProjectionCase', 7),
)


def git_sources(repo):
    paths = list(base.OWN_MODULES) + ['tools/community/' + name for name in TOOLS]
    body = subprocess.check_output(['git', '-C', str(repo), '-c', 'core.autocrlf=true',
        '-c', 'core.eol=crlf', 'archive', '--format=tar', 'HEAD', *paths])
    with tarfile.open(fileobj=io.BytesIO(body)) as archive:
        return {item.name: archive.extractfile(item).read() for item in archive.getmembers() if item.isfile()}


def verify_packets(root, source):
    current = read(root, 'community/source-files.json')
    require(current == read(root, 'cerro-reference/source-files.json') and len(current) == 361,
        'cold/native source packets differ or are not the exact 361-file block')
    previous = read(root, 'baseline-F/source-files.json')
    require(len(previous) == 355, 'accepted bootstrap F packet is incomplete')
    own = {name: value for name, value in current.items() if name.split('/')[0] in base.OWN_MODULES}
    expected = {name: sha(value) for name, value in source.items() if name.split('/')[0] in base.OWN_MODULES}
    require(own == expected and {name.split('/')[0] for name in own} == set(base.OWN_MODULES),
        'owned source files differ from the exact Git archive')
    require(set(current) == set(own) | {name for name in current if name.startswith(builder.MODULE + '/')},
        'source packet contains an unreviewed addon')
    unchanged = set(base.OWN_MODULES) - {'step_payroll_oca_api'}
    for module in unchanged:
        prefix = module + '/'
        require({name: value for name, value in current.items() if name.startswith(prefix)}
            == {name: value for name, value in previous.items() if name.startswith(prefix)},
            'addon outside the API block differs from bootstrap F: ' + module)
    prior_provider = {name: value for name, value in previous.items() if name.startswith(builder.MODULE + '/')}
    require(prior_provider == {name: value for name, value in current.items() if name.startswith(builder.MODULE + '/')},
        'cold provider changed from accepted bootstrap F')
    require(len(set(current) - set(previous)) == 6 and not set(previous) - set(current),
        'the packet is not bootstrap F plus six API files')
    return current, previous


def verify_provider(root, source, packet):
    original = base.addon_snapshot(root, 'original-provider')
    normal = base.addon_snapshot(root, 'normal-provider')
    cold = base.addon_snapshot(root, 'provider')
    require((len(original), len(normal), len(cold)) == (52, 52, 49), 'provider snapshots are incomplete')
    report = read(root, builder.REPORT)
    definitions = read(root, 'dependency-definitions.json')
    require(definitions['server_metadata_only'] is True and definitions['bodies_replayed_offline'] is False
        and definitions['dependency_hashes_match_derivation'] is True, 'dependency attestation scope differs')
    require(definitions['dependencies'] == report['dependencies']
        and definitions['definitions_sha256'] == builder.digest(definitions['definitions']),
        'external definition custody differs from the derivation')
    pin = json.loads(source['tools/community/simpledigital_runtime_source.json'].decode('utf-8-sig'))
    require(normal == replay_normal_provider(original), 'normal provider is not the exact trusted transformation of the pinned source')
    builder.verify_snapshots(original, normal, cold, report, definitions['definitions'], pin)
    base.tool_hash(report['builder_sha256'], 'build_original_bootstrap.py', source)
    base.tool_hash(report['normal_builder_sha256'], 'build_simpledigital_candidate.py', source)
    for module, entry in report['dependencies'].items():
        require(entry['license'] in ('LGPL-3', 'AGPL-3'), 'a dependency is not free software')
        if module in base.OWN_MODULES:
            expected = {name.split('/', 1)[1]: sha(body) for name, body in source.items() if name.startswith(module + '/')}
            require(entry['files'] == expected, 'owned dependency is not the reviewed Git export: ' + module)
    require({builder.MODULE + '/' + name: sha(body) for name, body in cold.items()}
        == {name: value for name, value in packet.items() if name.startswith(builder.MODULE + '/')},
        'cold provider differs from both executed packets')
    closure = report['closure']
    require(set(closure['omitted_files']) == set(builder.OMIT) and len(builder.OMIT) == 3
        and not closure['retained_salary_records'] and not closure['operational_payroll_package'],
        'the deferred-seed policy changed or claims operational payroll')
    require(closure['deferred_seed_assignment']['must_adopt_before_chile_processing']
        and closure['deferred_movement_catalogue']['must_adopt_before_movement_processing'],
        'an original configuration gate was removed')
    return report


def replay_normal_provider(original):
    """Replay the unchanged normal builder in memory, without executing artifacts."""
    result = dict(original)
    for name, body in original.items():
        if name == '__manifest__.py' or Path(name).suffix not in ('.xml', '.py', '.csv'):
            continue
        content = before = body.decode('utf-8-sig')
        for old, new in normal_builder.XMLIDS.items():
            content = content.replace(old, new)
        if name.endswith('.xml'):
            content = content.replace("@name='salary_computation'", "@name='computation'")
            content = content.replace("@name='hr_payroll'", "@name='payroll_settings'")
        if name in ('models/hr_contract.py', 'models/hr_employee.py'):
            tree = ast.parse(content)
            owners = {id(node.value): node.targets[0].id for node in ast.walk(tree)
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
            for node in ast.walk(tree):
                if owners.get(id(node)) in ('income_tax_type', 'work_schedule_id'):
                    continue
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == 'fields':
                    for keyword in node.keywords:
                        if keyword.arg == 'required' and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                            keyword.value = ast.Constant(False)
            content = ast.unparse(tree) + '\n'
        if name == 'views/hr_employee.xml':
            tree = ET.fromstring(content)
            for record in tree.iter('record'):
                if record.get('id') == 'view_employee_form_inherit_payslip_button':
                    for button in record.iter('button'):
                        if button.get('name') == 'action_view_payslips':
                            button.set('groups', 'hr.group_hr_user')
            content = ET.tostring(tree, encoding='unicode')
        if name == 'data/hr_salary_structure.xml':
            tree = ET.fromstring(content)
            for record in tree.iter('record'):
                if record.get('id') == 'structure_chile':
                    ET.SubElement(record, 'field', name='use_work_entries').text = 'True'
            content = ET.tostring(tree, encoding='unicode')
        if name == 'report/report_payslip_templates.xml':
            content = normal_builder.adapt_payslip_report_xml(content)
        if content != before:
            result[name] = content.encode('utf-8')
    manifest = ast.literal_eval(original['__manifest__.py'].decode('utf-8-sig'))
    manifest['depends'], manifest['version'] = ['step_simpledigital_oca_base'], '18.0.1.1.0'
    result['__manifest__.py'] = (repr(manifest) + '\n').encode('utf-8')
    return result


def engine_snapshot(root, folder):
    directory = safe_path(root, folder)
    if (directory / numeric.MODULE).is_dir():
        directory /= numeric.MODULE
    require(directory.is_dir(), 'engine snapshot is missing')
    manifest = safe_path(root, (directory / '__manifest__.py').relative_to(root))
    require(manifest.is_file() and ast.literal_eval(manifest.read_text(encoding='utf-8-sig')).get('license') == 'LGPL-3',
        'nonfree engine snapshot refused before reading its runtime bodies')
    files = {}
    for path in directory.rglob('*'):
        require(not path.is_symlink(), 'engine symlink is not evidence')
        if path.is_file():
            safe_path(root, path.relative_to(root))
            files[path.relative_to(directory).as_posix()] = path.read_bytes()
    return files


def git_object_oid(kind, body):
    return hashlib.sha1(kind.encode() + b' ' + str(len(body)).encode() + b'\0' + body).hexdigest()


def parse_git_tree(body):
    result, offset = [], 0
    while offset < len(body):
        space, nul = body.find(b' ', offset), body.find(b'\0', offset)
        require(offset < space < nul and nul + 21 <= len(body), 'malformed binary Git tree')
        mode, name = body[offset:space], body[space + 1:nul]
        require(mode in (b'40000', b'040000', b'100644', b'100755') and name
            and name not in (b'.', b'..') and b'/' not in name and b'\\' not in name,
            'unsafe Git tree mode or entry')
        result.append((mode, name.decode('utf-8'), body[nul + 1:nul + 21].hex()))
        offset = nul + 21
    require(len({name for _, name, _ in result}) == len(result), 'duplicate Git tree entry')
    return result


def verify_engine_git(proof, original):
    def decode(value):
        try:
            return base64.b64decode(value, validate=True)
        except (ValueError, TypeError) as exc:
            raise base.EvidenceError('malformed Git proof base64') from exc
    commit = decode(proof['commit_object_b64'])
    require(git_object_oid('commit', commit) == numeric.PIN, 'OCA commit object is not the pinned commit')
    headers = commit.split(b'\n\n', 1)[0].splitlines()
    trees = [line.split(b' ', 1)[1].decode('ascii') for line in headers if line.startswith(b'tree ')]
    require(len(trees) == 1 and re.fullmatch('[0-9a-f]{40}', trees[0]), 'commit has no unique root tree')
    root = decode(proof['root_tree_object_b64'])
    require(git_object_oid('tree', root) == trees[0], 'OCA root tree does not belong to the pinned commit')
    payroll = [entry for entry in parse_git_tree(root) if entry[1] == numeric.MODULE]
    require(len(payroll) == 1 and payroll[0][0] in (b'40000', b'040000'), 'pinned payroll subtree is absent')
    bodies = {oid: decode(value) for oid, value in proof['trees_by_oid_b64'].items()}
    require(all(re.fullmatch('[0-9a-f]{40}', oid) and git_object_oid('tree', body) == oid
        for oid, body in bodies.items()), 'Git subtree object hash differs')
    seen, files = set(), {}
    def visit(oid, prefix, ancestors=()):
        require(oid in bodies, 'Git payroll subtree proof is incomplete')
        require(oid not in ancestors, 'Git payroll subtree has a cycle')
        seen.add(oid)
        for mode, name, value in parse_git_tree(bodies[oid]):
            path = prefix + name
            if mode in (b'40000', b'040000'):
                visit(value, path + '/', ancestors + (oid,))
            else:
                require(path in original and git_object_oid('blob', original[path]) == value,
                    'engine original file is not a blob from the pinned commit: ' + path)
                files[path] = value
    visit(payroll[0][2], '')
    require(set(files) == set(original) and seen == set(bodies), 'Git payroll proof has missing or surplus files/trees')
    return {'commit': numeric.PIN, 'payroll_blob_count': len(files), 'tree_objects': len(seen),
        'all_original_blobs_bound_to_pinned_commit': True}


def verify_engine(root, source):
    original, candidate = engine_snapshot(root, 'engine-original'), engine_snapshot(root, 'engine-candidate')
    report = read(root, numeric.REPORT)
    base.tool_hash(report['builder_sha256'], 'build_numeric_input_engine.py', source)
    expected = numeric.plan(original)
    require(candidate == expected, 'engine candidate differs from the one supported keyword transformation')
    planned_report = numeric.report_for(original, expected)
    # The Git archive may use CRLF while Linux executed the same tool with LF.
    # Keep the actual admitted tool hash when reproducing its sealed receipt.
    planned_report['builder_sha256'] = report['builder_sha256']
    planned_report.pop('seal_sha256')
    planned_report['seal_sha256'] = numeric.seal(planned_report)
    require(report == planned_report, 'engine hashes, pin, seal or no-conversion flags differ')
    require(len(original) == len(candidate) == len(report['source_files']), 'engine file inventory differs')
    git_proof = verify_engine_git(read(root, 'engine-git-proof.json'), original)
    return {'source_files': len(original), 'candidate_files': len(candidate), 'oca_pin': numeric.PIN,
        'changed_files': [numeric.FILE], 'supported_keyword': report['supported_keyword'],
        'first_initialization_numeric': True, 'extra_digits_rounding': False,
        'pinned_git_object_proof': git_proof, 'remote_git_bodies_replayed_offline': True,
        'existing_float8_converted': False, 'historical_conversion': False}


def verify_executed_tools(root, source):
    directory = safe_path(root, 'executed-tools')
    require(directory.is_dir(), 'executed helper snapshots are missing')
    names = {path.name for path in directory.iterdir()}
    require(set(base.EXECUTED_TOOLS) | {'build_numeric_input_engine.py'} <= names <= set(TOOLS),
        'executed helper inventory is missing or unreviewed')
    for path in directory.iterdir():
        require(path.is_file() and not path.is_symlink(), 'executed helper is not a regular file')
        expected = source['tools/community/' + path.name]
        require(path.read_bytes().replace(b'\r\n', b'\n') == expected.replace(b'\r\n', b'\n'),
            'executed helper differs from Git: ' + path.name)


def verify_test_methods(source, log):
    classes = {}
    for name, classname, count in TEST_CLASSES:
        tree = ast.parse(source[name].decode('utf-8-sig'))
        matches = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == classname]
        require(len(matches) == 1, 'functional test class is not unique')
        methods = [node.name for node in matches[0].body if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
        require(len(methods) == count, 'functional test method count changed: ' + classname)
        for method in methods:
            require(len(re.findall(r'Starting ' + re.escape(classname + '.' + method) + r' \.\.\.', log)) == 1,
                'real functional test was not executed exactly once: ' + classname + '.' + method)
        classes[classname] = count
    require(sum(classes.values()) == 25, 'cold test classes do not add up to 25')
    return classes


def verify_cold(root, source, provider):
    cold, native = read(root, 'community/passed.json'), read(root, 'cerro-reference/passed.json')
    require(cold['counts'] == {'installed': 94, 'enterprise': 0} and cold['demo_installed_modules'] == 0
        and cold['without_demo'] == 'all' and cold['expected_test_count'] == 25
        and cold['numeric_input_engine'] is True, 'cold module/demo/functional graph differs')
    base.test_result(cold['test_results'], 25)
    base.no_flags(cold, ('operational_package', 'historical_conversion', 'original_masters_imported',
        'simpledigital_certified', 'financial_certified', 'writes_to_source', 'deferred_unpaid_membership_adopted'))
    require(cold['profile'] == provider['profile'] and cold['fixtures_rolled_back']
        and cold['registry_forms_defaults_acl_verified'] and cold['external_network_disabled']
        and cold['postgres_unix_socket'], 'cold execution provenance is incomplete')
    for mode, receipt, tests in (('community', cold, 25), ('cerro-reference', native, 294)):
        require(receipt['source_files_sha256'] == sha(safe_path(root, mode + '/source-files.json').read_bytes())
            and receipt['package_files'] == 361, 'receipt refers to another source packet')
        log = safe_path(root, mode + '/tests.log').read_text(errors='replace')
        require(not re.search(r' (ERROR|CRITICAL) ', log), 'functional log contains an error')
        base.test_result([line for line in log.splitlines() if 'tests.result' in line], tests)
    methods = verify_test_methods(source, safe_path(root, 'community/tests.log').read_text(errors='replace'))
    for key, name in (('runner_sha256', 'validate_original_bootstrap.py'), ('probe_sha256', 'probe_original_bootstrap.py')):
        base.tool_hash(cold[key], name, source)
    require(cold['bootstrap_derivation_sha256'] == sha(safe_path(root, builder.REPORT).read_bytes())
        and cold['numeric_engine_derivation_sha256'] == sha(safe_path(root, numeric.REPORT).read_bytes()),
        'cold receipt is not linked to both derivations')
    probe = read(root, 'community/registry-before.json')
    require(probe == read(root, 'community/registry-after.json'), 'cold registry/forms/defaults changed')
    require(probe['database'] == cold['database'] and probe['real_oca_engine'] and probe['normal_actor']
        and probe['actors_rolled_back'] and probe['official_structure_types'] == 4, 'real OCA actor/type evidence is incomplete')
    require(probe['input_columns'] == [['amount', 'numeric', False, False], ['code', 'character varying', True, False],
        ['contract_id', 'integer', True, False]], 'physical NUMERIC/NULL/required input contract differs')
    require(probe['salary_counts_before'] == probe['salary_counts_after'] and probe['salary_counts_before']
        and not any(probe['salary_counts_before'].values()), 'cold data were adopted or financial/history rows leaked')
    require(probe['officer_batch_read_denied'] and probe['internal_salary_rule_write_denied']
        and probe['visible_payroll_root'], 'cold ACL or navigation proof differs')
    base.no_flags(probe, ('deferred_unpaid_membership_adopted', 'original_masters_imported', 'operational_package',
        'historical_conversion', 'financial_certified', 'form_probe_created_payslips', 'form_probe_created_contracts'))
    base.tool_hash(probe['probe_sha256'], 'probe_original_bootstrap.py', source)
    return cold, native, methods


def verify_baseline(root):
    receipt = read(root, 'baseline-F/passed.json')
    base.test_result(receipt['test_results'], 12)
    require(receipt['expected_test_count'] == 12 and receipt['package_files'] == 355
        and receipt['source_files_sha256'] == sha(safe_path(root, 'baseline-F/source-files.json').read_bytes()),
        'baseline F receipt does not seal the previous 12-test packet')
    require(receipt['counts'] == {'installed': 94, 'enterprise': 0} and receipt['demo_installed_modules'] == 0,
        'baseline F is not the accepted cold profile')
    base.no_flags(receipt, ('operational_package', 'historical_conversion', 'original_masters_imported', 'writes_to_source'))
    summary = read(root, 'baseline-F/summary.json')
    require(summary['exact_packet_matches_git'] and summary['package_files'] == 355
        and summary['cold']['tests'] == 12 and summary['native_reference']['tests'] == 294,
        'baseline F summary does not describe the accepted 12/294 execution')
    base.no_flags(summary, ('original_masters_imported', 'operational_package', 'historical_conversion',
        'financial_certified', 'simpledigital_certified', 'deadline_resolved', 'artifact_code_executed'))


def verify_inventory(root, source):
    inventory = read(root, 'inventory/products-inventory.json')
    require(inventory['read_only'] is True, 'inventory is not readonly')
    base.no_flags(inventory, ('orm_loaded', 'business_data_exported', 'source_bodies_exported', 'enterprise_sources_copied'))
    base.tool_hash(inventory['tool_sha256'], 'audit_product_frontier.py', source)
    auditor = safe_path(root, 'inventory/auditor.py').read_bytes()
    require(auditor.replace(b'\r\n', b'\n') == source['tools/community/audit_product_frontier.py'].replace(b'\r\n', b'\n'),
        'inventory auditor snapshot differs from Git')
    require(set(inventory['products']) == {'cerro', 'steps', 'sys'}, 'inventory does not cover all production products')
    counts = {}
    for name, product in inventory['products'].items():
        modules = product['modules']
        require(len({row['name'] for row in modules}) == len(modules) == product['installed'],
            'installed inventory count/identity differs')
        require(sum(row['license'] == 'OEEL-1' for row in modules) == product['enterprise']
            and sum(row['name'].startswith('step') for row in modules) == product['own'],
            'inventory Enterprise/own counts differ from its module rows')
        counts[name] = {key: product[key] for key in ('installed', 'enterprise', 'own')}
    delta = read(root, 'inventory/inventory-delta.json')
    require(delta['read_only'] is True, 'inventory delta is not readonly')
    base.no_flags(delta, ('orm_loaded', 'database_writes'))
    require(delta['current_inventory_sha256'] == sha(safe_path(root, 'inventory/products-inventory.json').read_bytes()),
        'inventory delta references another inventory')
    original_bytes = safe_path(root, 'inventory/original-delta.json').read_bytes()
    original = read(root, 'inventory/original-delta.json')
    require(original['read_only'] is True and original['source_bodies_exported'] is False,
        'original inventory delta scope differs')
    require(delta == dict(original, current_inventory_sha256=original['current_sha256'], orm_loaded=False,
        database_writes=False, original_delta_sha256=sha(original_bytes)),
        'inventory alias or original delta seal/content differs')
    return {'products': counts, 'source': 'fresh_readonly_installed_module_metadata',
        'all_products_converted': False}


def verify(evidence, *, repo=None):
    root = Path(evidence).resolve()
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parents[2]
    source = git_sources(repo)
    base.tool_hash(sha(safe_path(root, 'collector.py').read_bytes()), 'collect_original_contracts.py', source)
    verify_executed_tools(root, source)
    packet, _ = verify_packets(root, source)
    verify_baseline(root)
    provider = verify_provider(root, source, packet)
    engine = verify_engine(root, source)
    base.verify_hr_derivation(root, source)
    cold, native, methods = verify_cold(root, source, provider)
    representation_path = safe_path(root, 'cerro-reference/business-representation-proof.json')
    if representation_path.is_file():
        base.tool_hash(read(root, 'cerro-reference/business-representation-proof.json')['tool_sha256'],
            'audit_stock_package_representation.py', source)
    preservation = base.verify_native(root, source, native)
    config_path = safe_path(root, 'configuration-preflight')
    gates = base.verify_preflight(root, source, cold, native) if config_path.exists() else {
        'fresh_preflight_collected': False, 'adopted': False,
        'remaining_gaps_not_recertified': {'fields': 7, 'physical': 5},
        'source_masters_not_adopted': 120, 'original_rules_not_adopted': 71}
    inputs = base.verify_input_storage(root, source) if safe_path(root, 'input-storage').exists() else {
        'previous_catalog_not_replayed': True, 'conversion_authorized': False}
    inventory = verify_inventory(root, source)
    return {'schema': 1, 'exact_packet_matches_git': True, 'package_files': 361,
        'owned_modules': 22, 'owned_modules_unchanged_from_bootstrap_F': 21,
        'provider_files': {'original': 52, 'normal': 52, 'cold': 49}, 'oca_numeric_engine': engine,
        'cold': {'tests': 25, 'test_classes': methods, 'installed': 94, 'enterprise': 0, 'demo': 0,
            'salary_rows': 0, 'original_masters_imported': False},
        'native_reference': {'tests': 294, 'installed': 391, 'enterprise': 140, **preservation},
        'prior_bootstrap_F': {'tests': 12, 'distinct_execution': True},
        'prior_normal_inputs_C': {'tests': 460, 'not_counted_as_new': True, 'not_replayed_in_this_block': True},
        'rule_projection': {'functional_cases': 7, 'explicit_source_pairs_only': True,
            'original_71_rule_identity_adopted': False, 'metadata_M2M_to_O2M_converted': False},
        'configuration': gates, 'prior_input_storage_catalog': inputs, 'inventory': inventory,
        'dependency_definitions': {'server_attested': True, 'dependency_bodies_replayed_offline': False},
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
    print('ORIGINAL_CONTRACTS_EVIDENCE_VERIFIED: cold 25 / native 294; original adoption remains pending')


if __name__ == '__main__':
    main()
