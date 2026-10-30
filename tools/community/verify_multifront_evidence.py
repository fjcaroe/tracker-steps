"""Offline custody for the exact normal-provider Community/native MF package.

No cold bootstrap, baseline F or 49-file provider is admitted. Artifact Python
is inert data; all replay/verification uses the trusted Git checkout only.
"""
import argparse
import ast
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

import build_original_bootstrap as builder
import build_numeric_input_engine as numeric
import hr_consumer_metadata as hr_metadata
import payroll_representation_contract as representation
import treasury_launcher_contract as treasury
import audit_multifront_installation as installation
import verify_original_bootstrap_evidence as base
import verify_original_contracts_evidence as previous


require, sha, read, safe_path = base.require, base.sha, base.read, base.safe_path
NEW_MODULES = ('step_account_treasury', 'step_treasury_community_reports',
               'step_account_treasury_reports', 'step_hr_contract_days', 'step_hr_contract_days_oca')
OWN_MODULES = base.OWN_MODULES + NEW_MODULES
EXECUTED_TOOLS = ('validate_payroll_api.py', 'offline_process.py', 'validate_agriculture_core.py',
    'validate_community_reports.py', 'manage_community_reports.py', 'hr_consumer_metadata.py',
    'treasury_launcher_contract.py', 'finance_frontier_contract.py', 'accelerated_acceptance.py',
    'hr_consumers_candidate.py', 'build_numeric_input_engine.py', 'build_simpledigital_candidate.py',
    'simpledigital_runtime_source.json', 'inspect_payroll_configuration.py')
TOOLS = tuple(dict.fromkeys(previous.TOOLS + EXECUTED_TOOLS + (
    'verify_original_contracts_evidence.py', 'verify_original_bootstrap_evidence.py',
    'verify_multifront_evidence.py', 'collect_multifront_evidence.py', 'audit_multifront_installation.py')))
EXPECTED_TESTS = {'community': 576, 'cerro-reference': 391}


def git_sources(repo):
    paths = list(OWN_MODULES) + ['tools/community/' + name for name in TOOLS]
    body = subprocess.check_output(['git', '-C', str(repo), '-c', 'core.autocrlf=true',
        '-c', 'core.eol=crlf', 'archive', '--format=tar', 'HEAD', *paths])
    with tarfile.open(fileobj=io.BytesIO(body)) as archive:
        return {item.name: archive.extractfile(item).read() for item in archive.getmembers() if item.isfile()}


def verify_packets(root, source):
    packets = [read(root, mode + '/source-files.json') for mode in EXPECTED_TESTS]
    require(packets[0] == packets[1], 'MF Community/native source packets differ')
    own = {name: sha(body) for name, body in source.items() if name.split('/')[0] in OWN_MODULES}
    require(len(OWN_MODULES) == 27 and {name.split('/')[0] for name in own} == set(OWN_MODULES),
            'MF must include exactly the 27 reviewed owned modules')
    pin = json.loads(source['tools/community/simpledigital_runtime_source.json'].decode('utf-8-sig'))
    for folder in ('original-provider', 'normal-provider'):
        path = safe_path(root, folder + '/__manifest__.py')
        require(ast.literal_eval(path.read_text(encoding='utf-8-sig'))['license'] == 'AGPL-3',
                'Nonfree provider refused before reading its runtime bodies')
    original = previous.base.addon_snapshot(root, 'original-provider')
    normal = previous.base.addon_snapshot(root, 'normal-provider')
    require(len(original) == len(normal) == len(pin['files']) == 52, 'MF requires the complete normal 52-file provider')
    for files in (original, normal):
        require(ast.literal_eval(files['__manifest__.py'].decode('utf-8-sig'))['license'] == 'AGPL-3', 'Nonfree provider refused')
    require({name: sha(body) for name, body in original.items()} == pin['files'], 'Original provider differs from its pinned source')
    require(normal == previous.replay_normal_provider(original), 'Normal provider is not the trusted exact derivation')
    expected = dict(own, **{builder.MODULE + '/' + name: sha(body) for name, body in normal.items()})
    require(packets[0] == expected, 'MF packet differs from exact Git sources/normal provider or contains an extra addon')
    return packets[0]


def verify_executed_tools(root, source):
    directory = safe_path(root, 'executed-tools')
    require(directory.is_dir() and {path.name for path in directory.iterdir()} == set(EXECUTED_TOOLS),
            'MF executed helper inventory differs')
    for name in EXECUTED_TOOLS:
        body = safe_path(root, 'executed-tools/' + name).read_bytes()
        require(body.replace(b'\r\n', b'\n') == source['tools/community/' + name].replace(b'\r\n', b'\n'),
                'Executed MF helper differs from Git: ' + name)
    base.tool_hash(sha(safe_path(root, 'collector.py').read_bytes()), 'collect_multifront_evidence.py', source)
    base.tool_hash(sha(safe_path(root, 'postflight-tools/audit_multifront_installation.py').read_bytes()),
                   'audit_multifront_installation.py', source)


def verify_file_manifest(root):
    receipt = read(root, 'evidence-files.json')
    require(receipt['schema'] == 1 and receipt['database_accessed'] is False
            and receipt['database_writes'] is False and receipt['dump_exported'] is False
            and receipt['enterprise_source_bodies_exported'] is False, 'MF collector custody/scope differs')
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'MF evidence symlink refused')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(actual == set(receipt['files']) | {'evidence-files.json'}, 'MF capsule file inventory differs')
    for name, digest in receipt['files'].items():
        require(sha(safe_path(root, name).read_bytes()) == digest, 'MF capsule member hash differs: ' + name)


def critical_methods(source, log, mode):
    modules = NEW_MODULES if mode == 'community' else NEW_MODULES[:-1]
    selected = [(name, None) for name in source if '/tests/test_' in name and name.endswith('.py')
                and name.split('/')[0] in modules]
    selected += [('step_l10n_cl_edi_core/tests/test_ted.py', 'TestTEDCore')]
    caf_module = 'step_l10n_cl_caf_storage' if mode == 'community' else 'step_l10n_cl_caf_native_reference'
    # File names are source-driven; only the explicit TED test class is added.
    selected += [(name, 'TestTEDCustodyStorage' if mode == 'community' else 'TestTEDNativeCAFCustody')
                 for name in source if name.startswith(caf_module + '/tests/') and name.endswith('.py')]
    result = {}
    for name, only_class in selected:
        require(name in source, 'Critical MF test source missing: ' + name)
        for cls in ast.parse(source[name].decode('utf-8-sig')).body:
            if not isinstance(cls, ast.ClassDef) or only_class and cls.name != only_class:
                continue
            for method in cls.body:
                if isinstance(method, ast.FunctionDef) and method.name.startswith('test_'):
                    key = cls.name + '.' + method.name
                    require(key not in result and len(re.findall(r'Starting ' + re.escape(key) + r' \.\.\.', log)) == 1,
                            'Critical functional MF method did not run exactly once: ' + key)
                    result[key] = name
    require(len(result) == (103 if mode == 'community' else 97), 'Critical MF method inventory changed')
    return len(result)


def verify_receipt(root, source, packet, mode):
    receipt = read(root, mode + '/passed.json')
    expected = EXPECTED_TESTS[mode]
    require(receipt.get('focused_development_pass') is False, 'Focused development execution is not acceptance')
    require(receipt['mode'] == mode and receipt['profile'] == 'simpledigital' and receipt['accelerated'] is True
            and receipt['custody_grouping'] is True and receipt['multifront'] is True,
            'A diagnostic or different profile is not MF acceptance')
    require(receipt['expected_test_count'] == expected and receipt['package_files'] == len(packet)
            and receipt['source_files_sha256'] == sha(safe_path(root, mode + '/source-files.json').read_bytes()),
            'MF receipt does not bind exact test/source packet')
    graph = read(root, 'graph-admission.json')
    require(graph['source'] == 'independently_measured_by_coordinator'
            and type(graph[mode]['installed']) is int and graph[mode]['installed'] > (0 if mode == 'community' else 140)
            and graph[mode]['enterprise'] == (0 if mode == 'community' else 140)
            and receipt['counts'] == graph[mode],
            'MF runtime edition/installed graph evidence differs')
    require(receipt['oca_revision'] == numeric.PIN and receipt['payroll_model_registered'] is True,
            'Real pinned payroll model is missing')
    require(receipt['numeric_input_engine'] is (mode == 'community'), 'MF NUMERIC overlay scope differs')
    require(receipt['official_community_revision'] == (builder.PIN_COMMUNITY if mode == 'community' else None),
            'MF official Community runtime pin differs')
    if mode == 'community':
        require(receipt['numeric_engine_derivation_sha256'] == sha(safe_path(root, numeric.REPORT).read_bytes()),
                'MF receipt does not bind the executed engine derivation')
    require(receipt['external_network_disabled'] is True and receipt['loopback_http_only'] is True
            and receipt['postgres_unix_socket'] is True, 'MF isolation evidence is incomplete')
    base.no_flags(receipt, ('writes_to_source', 'historical_conversion', 'simpledigital_certified'))
    for flag in ('financial_certified', 'operational_package', 'original_masters_imported', 'deadline_resolved'):
        require(flag not in receipt or receipt[flag] is False, 'MF receipt claims unsupported conversion/certification')
    for key, name in (('validator_sha256', 'validate_payroll_api.py'), ('offline_runner_sha256', 'offline_process.py'),
                      ('identity_snapshot_tool_sha256', 'validate_agriculture_core.py')):
        base.tool_hash(receipt[key], name, source)
    require(set(receipt['accelerated_tools_sha256']) == {'accelerated_acceptance.py', 'hr_consumers_candidate.py',
            'finance_frontier_contract.py', 'hr_consumer_metadata.py'}, 'MF accelerated helper inventory differs')
    for name, digest in receipt['accelerated_tools_sha256'].items():
        base.tool_hash(digest, name, source)
    base.test_result(receipt['test_results'], expected)
    log = safe_path(root, mode + '/tests.log').read_text(errors='replace')
    require(not re.search(r' (ERROR|CRITICAL) ', log), 'MF functional log contains an error')
    base.test_result([line for line in log.splitlines() if 'tests.result' in line], expected)
    methods = critical_methods(source, log, mode)
    installed_proof = read(root, mode + '/module-installation.json')
    base.tool_hash(installed_proof['tool_sha256'], 'audit_multifront_installation.py', source)
    require(tuple(installation.OWN_MODULES) == OWN_MODULES, 'Installation postflight packet scope differs')
    installation_summary = installation.verify(installed_proof, mode, source, receipt)
    finance = read(root, mode + '/finance-frontier.json')
    finance_modules = ('step_account_balance_analytic', 'step_bank_export_core', 'step_accounting_multicurrency_core')
    if mode != 'community':
        finance_modules += ('step_account_treasury_batch', 'step_bank_security', 'step_accounting_multicurrency')
    versions = {module: ast.literal_eval(source[module + '/__manifest__.py'].decode('utf-8-sig'))['version'] for module in finance_modules}
    require(finance['mode'] == ('community' if mode == 'community' else 'cerro-copy')
            and finance['versions'] == versions and len(finance['aliases']) == (13 if mode == 'community' else 15)
            and len(finance['multicurrency_legacy_aliases']) == 37
            and finance['draft_grouping_provider'] is True and finance['payment_formats_use_original_model'] is True
            and finance['batch_conversion_certified'] is False and finance['writes_to_source'] is False,
            'MF actual finance registry evidence differs')
    configuration = read(root, mode + '/configuration.json')
    require(configuration['database'] == receipt['database'] and configuration['normal_actor'] is True
            and configuration['read_only_configuration'] is True and configuration['fixtures_rolled_back'] is True
            and configuration['financial_certified'] is False and configuration['writes_to_source'] is False,
            'MF actual configuration inspection custody differs')
    if mode == 'community':
        pdf = read(root, mode + '/stored-payslip-pdf.json')
        require(receipt['stored_payslip_pdf_reports'] == pdf['actual_pdf_count'] == len(pdf['proofs']) == 2
                and pdf['financial_certified'] is False, 'MF actual stored-line PDF evidence differs')
        for proof in pdf['proofs']:
            require(proof['normal_employee'] and proof['stored_history_unchanged'] and not proof['missing_assets']
                    and proof['pages'] > 0 and Path(proof['file']).name == proof['file'], 'MF PDF actor/history/assets differ')
            body = safe_path(root, mode + '/payslip-pdf-evidence/' + proof['file']).read_bytes()
            require(body.startswith(b'%PDF-') and sha(body) == proof['sha256'], 'MF actual PDF bytes differ')
    return receipt, {'tests': expected, 'critical_multifront_methods': methods,
                     'module_installation': installation_summary, **receipt['counts']}


def verify_preservation(root, source, native, repo):
    admission = read(root, 'cerro-reference/version-admission.json')
    require(admission, 'MF native upgrade version admission is missing')
    for module, row in admission.items():
        require(module in OWN_MODULES and row['downgrade'] is False
                and row['candidate'] == ast.literal_eval(source[module + '/__manifest__.py'].decode('utf-8-sig'))['version'],
                'MF native candidate version differs from Git')
        require(all(isinstance(row[key], str) and re.fullmatch(r'[0-9]+(?:\.[0-9]+)*', row[key]) for key in ('original', 'candidate'))
                and tuple(map(int, row['candidate'].split('.'))) >= tuple(map(int, row['original'].split('.'))),
                'MF native version downgrade refused')
    before, upgraded, after = [read(root, 'cerro-reference/business-' + name + '.json')
                               for name in ('before', 'after-upgrade', 'after')]
    require(len(before) >= 1061 and before.keys() == upgraded.keys() == after.keys(), 'MF original business/counter inventory changed')
    counters = [name for name in before if re.fullmatch(r'ir_sequence_[0-9]+(_[0-9]+)?', name)]
    require(len(counters) >= 140 and all(before[name] == upgraded[name] == after[name] for name in counters),
            'MF original sequence/counter changed')
    differences = {name for name in before if before[name] != upgraded[name] or before[name] != after[name]}
    representation_audit = None
    if differences:
        require(differences == {representation.TABLE}, 'Original business data changed beyond the exact stock representation witness')
        proof = read(root, 'cerro-reference/business-representation-proof.json')
        require(proof['database'] == native['database'] and proof['source_dump_sha256'] == read(root, 'source-dump.json')['sha256'],
                'MF stock witness is not from this fresh native database/backup')
        require(proof['native_acceptance_sha256'] == sha(safe_path(root, 'cerro-reference/passed.json').read_bytes())
                and proof['expected_multifront_installed'] == read(root, 'graph-admission.json')['cerro-reference']['installed'],
                'MF stock witness does not bind the accepted native receipt/measured graph')
        base.tool_hash(proof['tool_sha256'], 'audit_stock_package_representation.py', source)
        base.tool_hash(proof['snapshot_normalizer_tool_sha256'], 'validate_community_reports.py', source)
        representation_audit = representation.verify(before[representation.TABLE], upgraded[representation.TABLE], after[representation.TABLE], proof)
        require(proof['comparison'] == representation_audit, 'MF stock representation classification differs')
    require(read(root, 'cerro-reference/history-before.json') == read(root, 'cerro-reference/history-after.json'), 'MF original history/expiration changed')
    original, current = read(root, 'cerro-reference/identity-before.json'), read(root, 'cerro-reference/identity-after.json')
    raw_current = deepcopy(current)
    require(native['original_xmlid_noupdate_captured'] and all('noupdate' in row for row in original['original_xmlids']),
            'Original XMLID noupdate evidence missing')
    treasury_audit, normalized = treasury.verify(original, current, read(root, 'cerro-reference/treasury-before.json'),
        read(root, 'cerro-reference/treasury-after.json'), repo)
    captured = read(root, 'cerro-reference/treasury-metadata-proof.json')
    for name, digest in captured['source']['files_sha256'].items():
        require(name in source and digest in {sha(source[name]), sha(source[name].replace(b'\r\n', b'\n'))},
                'Treasury proof source differs from Git')
    treasury_audit['source']['files_sha256'] = captured['source']['files_sha256']
    require(treasury_audit == captured and current == raw_current, 'Treasury policy/raw identity custody differs')
    hr_audit = hr_metadata.verify(original, normalized)
    captured_hr = read(root, 'cerro-reference/hr-metadata-proof.json')
    path = captured_hr['source']['path']
    require(captured_hr['source']['sha256'] in {sha(source[path]), sha(source[path].replace(b'\r\n', b'\n'))}, 'HR proof source differs from Git')
    hr_audit['source']['sha256'] = captured_hr['source']['sha256']
    require(hr_audit == captured_hr, 'HR metadata exceptions differ from the trusted exact policy')
    for table, rows in original.items():
        if table == 'ir_model_fields':
            continue  # Every original field and its exact three exceptions were checked above.
        now = normalized[table]
        if rows and 'id' in rows[0]:
            index = {row['id']: row for row in now}
            require(len(index) == len(now) and all(index.get(row['id']) == row for row in rows), 'Original MF identity changed: ' + table)
        else:
            require(all(row in now for row in rows), 'Original MF relation changed: ' + table)
    from finance_frontier_contract import verify_metadata
    bank_audit = verify_metadata(read(root, 'cerro-reference/bank-metadata-before.json'), read(root, 'cerro-reference/bank-metadata-after.json'))
    require(bank_audit == read(root, 'cerro-reference/bank-metadata-proof.json'), 'Bank identity policy differs')
    return {'business_contracts': len(before), 'original_counters_exact': len(counters),
            'exact_snapshot_contracts': len(before) - len(differences), 'history_exact': True,
            'raw_identity_unchanged': True, 'identity_rows': {name: len(rows) for name, rows in original.items()},
            'treasury': treasury_audit, 'hr_metadata': hr_audit, 'bank_metadata': bank_audit,
            'representation_audit': representation_audit}


def verify_inventory(root, source):
    inventory = read(root, 'inventory/products-inventory.json')
    require(inventory['read_only'] is True, 'MF inventory is not readonly')
    base.no_flags(inventory, ('orm_loaded', 'business_data_exported', 'source_bodies_exported', 'enterprise_sources_copied'))
    base.tool_hash(inventory['tool_sha256'], 'audit_product_frontier.py', source)
    require(safe_path(root, 'inventory/auditor.py').read_bytes().replace(b'\r\n', b'\n')
            == source['tools/community/audit_product_frontier.py'].replace(b'\r\n', b'\n'), 'MF inventory auditor differs')
    require(set(inventory['products']) == {'cerro', 'steps', 'sys'}, 'MF inventory does not cover all three products')
    result = {}
    for name, product in inventory['products'].items():
        modules = product['modules']
        require(len(modules) == product['installed'] == len({row['name'] for row in modules})
                and sum(row['license'] == 'OEEL-1' for row in modules) == product['enterprise']
                and sum(row['name'].startswith('step') for row in modules) == product['own'], 'MF product inventory rows/counts differ')
        result[name] = {key: product[key] for key in ('installed', 'enterprise', 'own')}
    return result


def verify(evidence, *, repo=None):
    root = Path(evidence).resolve()
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parents[2]
    source = git_sources(repo)
    verify_file_manifest(root)
    verify_executed_tools(root, source)
    packet = verify_packets(root, source)
    # This provider is private AGPL source, not a repository addon. Its entire
    # 52-file replay was validated above before its manifest joins the trusted
    # postflight source map.
    source.update({builder.MODULE + '/' + name: body
                   for name, body in base.addon_snapshot(root, 'normal-provider').items()})
    engine = previous.verify_engine(root, source)
    require(engine['source_files'] == engine['candidate_files'] == 144, 'MF NUMERIC engine file inventory differs')
    base.verify_hr_derivation(root, source)
    community, community_summary = verify_receipt(root, source, packet, 'community')
    native, native_summary = verify_receipt(root, source, packet, 'cerro-reference')
    preservation = verify_preservation(root, source, native, repo)
    return {'schema': 1, 'profile': 'multifront-normal-provider', 'exact_packet_matches_git': True,
            'package_files': len(packet), 'owned_modules': 27, 'normal_provider_files': 52,
            'oca_numeric_engine': engine, 'community': community_summary, 'native_reference': native_summary,
            'preservation': preservation, 'inventory': verify_inventory(root, source),
            'cold_bootstrap_claimed': False, 'original_masters_imported': False, 'operational_package': False,
            'historical_conversion': False, 'financial_certified': False, 'simpledigital_certified': False,
            'deadline_resolved': False, 'artifact_code_executed': False, 'verifier_sha256': sha(Path(__file__).read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.evidence)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print('MULTIFRONT_EVIDENCE_VERIFIED: Community 576 / native 391; integral conversion remains pending')


if __name__ == '__main__':
    main()
