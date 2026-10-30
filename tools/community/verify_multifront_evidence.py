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
import tempfile
from urllib.parse import unquote

import build_original_bootstrap as builder
import build_numeric_input_engine as numeric
import hr_consumer_metadata as hr_metadata
import payroll_representation_contract as representation
import treasury_launcher_contract as treasury
import audit_multifront_installation as installation
import oca_vendor_contract as vendor
import quality_vendor_contract as quality_vendor
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


def own_modules(operational_extensions=False, quality_extension=False):
    require(type(operational_extensions) is bool and type(quality_extension) is bool
        and (not quality_extension or operational_extensions), 'Quality requires explicit operational extensions')
    return OWN_MODULES + (installation.EXTENSION_MODULES if operational_extensions else ()) + (installation.QUALITY_MODULES if quality_extension else ())


def expected_tests(operational_extensions=False, quality_extension=False, critical_extension=False, critical_generation='R3'):
    require(type(operational_extensions) is bool, 'Explicit operational extensions profile required')
    own_modules(operational_extensions, quality_extension)
    require(type(critical_extension) is bool and (not critical_extension or quality_extension), 'Critical requires Quality profile')
    installation.critical_tests(critical_extension, critical_generation)
    return installation.critical_tests(critical_extension, critical_generation) if critical_extension else installation.QUALITY_TESTS if quality_extension else installation.EXTENSION_TESTS if operational_extensions else EXPECTED_TESTS


def expected_alias_contract(aliases):
    """MF includes the real manual bank setup provider in both registries.

    Resolve the expected API from the trusted finance checker, not a prior
    Community module-graph length. Runtime lookup/field-type checks remain in
    that checker; this seals every emitted alias and its shared-model identity.
    """
    from finance_frontier_contract import LEGACY_XMLIDS
    expected = {module + '.' + name for module, names in LEGACY_XMLIDS.items() for name in names}
    require(isinstance(aliases, dict) and set(aliases) == expected, 'MF finance alias set differs from the complete legacy contract')
    require(all(type(value) is int and value > 0 for value in aliases.values()), 'MF finance alias reference is not a positive record ID')
    model_names = [module + '.model_res_partner_bank' for module in LEGACY_XMLIDS]
    require(len({aliases[name] for name in model_names}) == 1, 'MF shared banking model aliases target different references')
    for prefix in ('field_', 'selection__', 'view_'):
        names = [module + '.' + name for module, values in LEGACY_XMLIDS.items() for name in values if name.startswith(prefix)]
        require(len({aliases[name] for name in names}) == len(names), 'MF distinct banking metadata aliases share a wrong reference')
    return {'exact_legacy_aliases': len(expected),
            'manual_setup_related_field_aliases': sum('.field_account_setup_bank_manual_config__' in name for name in expected),
            'shared_bank_model_reference_exact': True}


def git_sources(repo, *, operational_extensions=False, quality_extension=False):
    paths = list(own_modules(operational_extensions, quality_extension)) + ['tools/community/' + name
        for name in TOOLS + (('oca_vendor_contract.py',) if operational_extensions else ())
        + (('quality_vendor_contract.py', 'verify_original_report_headers.py') if quality_extension else ())]
    body = subprocess.check_output(['git', '-C', str(repo), '-c', 'core.autocrlf=true',
        '-c', 'core.eol=crlf', 'archive', '--format=tar', 'HEAD', *paths])
    with tarfile.open(fileobj=io.BytesIO(body)) as archive:
        return {item.name: archive.extractfile(item).read() for item in archive.getmembers() if item.isfile()}


def verify_packets(root, source, *, operational_extensions=False, quality_extension=False):
    packets = [read(root, mode + '/source-files.json') for mode in EXPECTED_TESTS]
    require(packets[0] == packets[1], 'MF Community/native source packets differ')
    modules = own_modules(operational_extensions, quality_extension)
    own = {name: sha(body) for name, body in source.items() if name.split('/')[0] in modules}
    require(len(modules) == (33 if quality_extension else 30 if operational_extensions else 27) and {name.split('/')[0] for name in own} == set(modules),
            'MF must include the exact reviewed owned module profile')
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


def verify_executed_tools(root, source, *, operational_extensions=False, quality_extension=False):
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
    if operational_extensions:
        base.tool_hash(sha(safe_path(root, 'vendor-auditor.py').read_bytes()), 'oca_vendor_contract.py', source)
    if quality_extension:
        base.tool_hash(sha(safe_path(root, 'quality-vendor-auditor.py').read_bytes()), 'quality_vendor_contract.py', source)
        base.tool_hash(sha(safe_path(root, 'original-report-header-reviewer.py').read_bytes()), 'verify_original_report_headers.py', source)


def verify_file_manifest(root, *, operational_extensions=False, quality_extension=False, critical_extension=False, critical_generation='R3'):
    receipt = read(root, 'evidence-files.json')
    installation.check_generation(receipt, critical_extension, critical_generation)
    require(receipt.get('critical_extension', False) is critical_extension, 'Exact critical evidence manifest flag required')
    require(receipt['schema'] == 1 and receipt['database_accessed'] is False
            and receipt['database_writes'] is False and receipt['dump_exported'] is False
            and receipt['enterprise_source_bodies_exported'] is False
            and receipt.get('operational_extensions', False) is operational_extensions
            and receipt.get('quality_extension', False) is quality_extension, 'MF collector custody/scope differs')
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'MF evidence symlink refused')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(actual == set(receipt['files']) | {'evidence-files.json'}, 'MF capsule file inventory differs')
    for name, digest in receipt['files'].items():
        require(sha(safe_path(root, name).read_bytes()) == digest, 'MF capsule member hash differs: ' + name)


def critical_methods(source, log, mode, *, operational_extensions=False, quality_extension=False, critical_extension=False, critical_generation='R3'):
    installation.critical_tests(critical_extension, critical_generation)
    modules = NEW_MODULES if mode == 'community' else NEW_MODULES[:-1]
    selected = [(name, None) for name in source if '/tests/test_' in name and name.endswith('.py')
                and name.split('/')[0] in modules]
    selected += [('step_l10n_cl_edi_core/tests/test_ted.py', 'TestTEDCore')]
    caf_module = 'step_l10n_cl_caf_storage' if mode == 'community' else 'step_l10n_cl_caf_native_reference'
    # File names are source-driven; only the explicit TED test class is added.
    selected += [(name, 'TestTEDCustodyStorage' if mode == 'community' else 'TestTEDNativeCAFCustody')
                 for name in source if name.startswith(caf_module + '/tests/') and name.endswith('.py')]
    if operational_extensions:
        selected += [('step_l10n_cl_edi_core/tests/test_dte_signature.py', 'TestDTESignatureCore'),
                     ('step_l10n_cl_edi_core/tests/test_envelope.py', 'TestEnvioDTECore'),
                     (caf_module + '/tests/test_dte_signature.py',
                      'TestDTESignatureCustodyStorage' if mode == 'community' else 'TestDTESignatureNativeCAFCustody'),
                     ('step_batch_payment_grouping/tests/test_posting.py', 'BatchDraftPaymentPostingCase')]
        if mode == 'community':
            selected += [('step_payroll_advantages_oca/tests/test_advantages.py', 'ContractAdvantageCase'),
                         ('step_payroll_original_report/tests/test_route.py', 'OriginalPayrollReportRouteCase'),
                         ('step_payroll_original_report/tests/test_pdf.py', 'OriginalPayrollReportPdfCase')]
        else:
            selected += [('step_payroll_benefits_native_reference/tests/test_native_benefits.py', 'NativeBenefitReferenceCase'),
                         ('step_payroll_original_report/tests/test_route.py', 'NativeOriginalPayrollReportRouteCase')]
    if quality_extension:
        selected += [('step_quality_oca/tests/test_inspection.py', 'QualityOcaOperationCase')] if mode == 'community' else [
            ('step_qa_native_reference/tests/test_native_quality.py', 'NativeQualityConsumerCase')]
    require(type(critical_extension) is bool and (not critical_extension or quality_extension), 'Critical methods require Quality profile')
    if critical_extension:
        selected += [('step_batch_payment_grouping/tests/test_application.py', 'BatchInvoiceApplicationCase')]
    if critical_extension and mode == 'community':
        selected += [('step_payroll_oca_api/tests/test_original_nullable.py', 'OriginalNullableCase'),
                     ('step_payroll_oca_api/tests/test_original_rule_projection.py', 'OriginalRuleProjectionCase')]
    if critical_generation == 'S' and mode == 'community':
        selected += [('step_payroll_oca_api/tests/test_original_input_type_ui.py', 'OriginalInputTypeUICase')]
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
    if operational_extensions and mode == 'community':
        keys = ['BatchCoreCase.test_form_offers_real_ledger_posting_without_batch_validation']
        if critical_extension:
            keys.append('BatchCoreCase.test_normal_form_applies_only_saved_complete_document_links')
        name = 'step_batch_payment_core/tests/test_core.py'
        for key in keys:
            require(name in source and any(isinstance(cls, ast.ClassDef) and cls.name == 'BatchCoreCase'
                and any(isinstance(method, ast.FunctionDef) and cls.name + '.' + method.name == key for method in cls.body)
                for cls in ast.parse(source[name].decode('utf-8-sig')).body), 'Posting form method missing from trusted source')
            require(key not in result and len(re.findall(r'Starting ' + re.escape(key) + r' \.\.\.', log)) == 1,
                    'Critical posting form did not run exactly once')
            result[key] = name
    count = (173 if mode == 'community' else 147) if quality_extension else (164 if mode == 'community' else 143) if operational_extensions else (103 if mode == 'community' else 97)
    if critical_extension:
        count += 5 + (28 if mode == 'community' else 11)  # PKIX, HR admission/projection and invoice application.
    if critical_generation == 'S':
        count += 6 if mode == 'community' else 5
    require(len(result) == count, 'Critical MF method inventory changed')
    return len(result)


def original_pdf_inventory(directory, *, repeated=False):
    """Exact inert capture inventory. Never execute captured HTML or code."""
    directory = Path(directory)
    proof = read(directory, 'proof.json')
    files = {'proof.json': safe_path(directory, 'proof.json')}

    def member(name, *, entry=None, suffix=None):
        require(isinstance(name, str) and '\\' not in name and ':' not in name, 'Unsafe original PDF member')
        path = safe_path(directory, name)
        require(path.is_file() and (suffix is None or path.suffix == suffix), 'Original PDF member type/missing file')
        body = path.read_bytes()
        if entry is not None:
            require(type(entry['bytes']) is int and entry['bytes'] == len(body)
                and entry['sha256'] == sha(body), 'Original PDF pipeline member hash/bytes differ')
        if name in files:
            require(files[name] == path, 'Conflicting original PDF member')
        files[name] = path
        return body

    if not repeated:
        require(isinstance(proof['file'], str) and Path(proof['file']).name == proof['file'], 'Original PDF filename scope differs')
        member(proof['file'], entry=proof, suffix='.pdf')
    else:
        repetitions = proof.get('repetitions')
        require(isinstance(repetitions, list) and len(repetitions) == 3 and proof.get('header_layout_accepted') is False
            and all(isinstance(proof.get(name), str) and proof[name] for name in ('company_name', 'country_name')),
            'Three real original-report repetitions and outstanding header layout required')
        require(sha(member('preview.html', suffix='.html')) == proof['financial_verified_html_sha256'], 'Original PDF preview hash differs')
        capture = proof.get('asset_capture')
        require(isinstance(capture, dict) and set(capture) == {'file', 'sha256', 'bytes'}
            and capture['file'] == 'assets.json', 'Exact original PDF asset-capture receipt required')
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, 'Duplicate original PDF asset metadata key')
                result[key] = value
            return result
        assets = json.loads(member('assets.json', entry=capture, suffix='.json'), object_pairs_hook=unique_object)
        require(isinstance(assets, dict) and assets and set(assets) == set(proof['runtime_asset_sha256']),
            'Original PDF captured asset URL set differs from runtime')
        for url, entry in assets.items():
            decoded = unquote(url) if isinstance(url, str) else ''
            require(isinstance(url, str) and url.startswith('/') and not decoded.startswith('//')
                and not any(value in url or value in decoded for value in ('\\', '?', '#', ':', '\x00', '\r', '\n'))
                and not any(value.isspace() for value in decoded) and '..' not in decoded.split('/')
                and not decoded.lower().endswith(('.py', '.pyc', '.pyo')),
                'Unsafe/non-runtime/source URL in original PDF asset capture')
            require(isinstance(entry, dict) and set(entry) == {'file', 'sha256', 'bytes', 'content_type'}
                and isinstance(entry['sha256'], str) and re.fullmatch('[0-9a-f]{64}', entry['sha256'])
                and entry['sha256'] == proof['runtime_asset_sha256'][url]
                and entry['file'] == 'assets/' + entry['sha256'] + '.bin',
                'Original PDF asset digest/path/deduplication differs')
            mime = entry['content_type']
            require(isinstance(mime, str) and re.fullmatch(r'[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+(?:;[ ]*charset=[A-Za-z0-9._-]+)?', mime)
                and mime.split(';', 1)[0].lower() not in ('text/x-python', 'application/x-python', 'text/x-python-script'),
                'Original PDF asset content type/credential scope differs')
            member(entry['file'], entry=entry, suffix='.bin')
        require(all(proof[key] == repetitions[0][key] for key in ('file', 'sha256', 'bytes', 'pages')),
            'First original PDF and compatibility receipt differ')
        names = set()
        for index, repetition in enumerate(repetitions, 1):
            filename = repetition['file']
            require(isinstance(filename, str) and Path(filename).name == filename and filename not in names,
                'Repeated original PDF filenames must be distinct')
            names.add(filename)
            body = member(filename, entry=repetition, suffix='.pdf')
            require(body.startswith(b'%PDF-') and type(repetition['pages']) is int and repetition['pages'] > 0
                and all(type(repetition[key]) is int and repetition[key] == 1 for key in ('prepared_headers', 'wkhtmltopdf_runs', 'argument_calls'))
                and all(repetition[key] is True for key in ('company_present_in_prepared_headers', 'country_present_in_prepared_headers', 'normal_run_actor')),
                'Original PDF repetition/actor/pipeline count differs')
            prefix = 'repetition-%s/' % index
            require(repetition['pipeline'] == prefix + 'pipeline.json', 'Original PDF repetition pipeline scope differs')
            raw = member(repetition['pipeline'], entry={'bytes': repetition['pipeline_bytes'], 'sha256': repetition['pipeline_sha256']}, suffix='.json')
            pipeline = json.loads(raw)
            require(set(pipeline) == {'prepare_calls', 'run_calls', 'argument_calls'}
                and all(isinstance(pipeline[key], list) and len(pipeline[key]) == 1 for key in pipeline), 'Actual original PDF pipeline calls differ')
            prepared, run, arguments = (pipeline[key][0] for key in ('prepare_calls', 'run_calls', 'argument_calls'))
            require(set(prepared) == {'environment', 'report_model', 'html', 'bodies', 'header', 'footer', 'document_ids',
                'specific_paperformat_args', 'company_name_present', 'country_name_present', 'embedded_images'}
                and set(run) == {'environment', 'bodies', 'header', 'footer', 'landscape', 'specific_paperformat_args', 'set_viewport_size'},
                'Unexpected original PDF prepare/conversion capture scope')
            require(prepared['company_name_present'] is True and prepared['country_name_present'] is True,
                'Actual prepared company/country evidence differs from repetition receipt')
            for call in (prepared, run, arguments):
                environment = call['environment']
                require(set(environment) == {'uid', 'sudo', 'allowed_company_ids'}
                    and type(environment['uid']) is int and environment['uid'] > 0
                    and type(environment['sudo']) is bool and isinstance(environment['allowed_company_ids'], list)
                    and all(type(value) is int and value > 0 for value in environment['allowed_company_ids']),
                    'Unexpected original PDF environment/session capture')
            for call in (run, arguments):
                require(type(call['environment']['uid']) is int and call['environment']['uid'] == proof['actor_id']
                    and call['environment']['sudo'] is False, 'Original PDF converter changed the normal actor')
            require(arguments.get('session_arguments_captured') is False and isinstance(arguments['arguments'], list)
                and all(isinstance(value, str) and value.split('=', 1)[0].lower() not in
                    ('--cookie', '--cookie-jar', '--username', '--password') for value in arguments['arguments']),
                'Session/cookie/credential converter arguments refused')
            allowed = {'environment', 'paperformat', 'landscape', 'specific_paperformat_args',
                'set_viewport_size', 'arguments', 'session_arguments_captured'}
            require(set(arguments) == allowed, 'Unexpected original PDF argument capture scope')
            for call in (prepared, run):
                require(isinstance(call['bodies'], list) and call['bodies'], 'Original PDF body capture is absent')
                for entry in [call['header'], call['footer'], *call['bodies']]:
                    require(isinstance(entry['file'], str) and Path(entry['file']).name == entry['file'], 'Original PDF HTML member escapes its repetition')
                    member(prefix + entry['file'], entry=entry, suffix='.html')
            require(isinstance(prepared['html']['file'], str) and Path(prepared['html']['file']).name == prepared['html']['file'], 'Original PDF prepare HTML scope differs')
            member(prefix + prepared['html']['file'], entry=prepared['html'], suffix='.html')
            require(all(prepared[key]['sha256'] == run[key]['sha256'] and prepared[key]['bytes'] == run[key]['bytes']
                for key in ('header', 'footer')), 'Prepared and converted original PDF headers/footers differ')
    actual = set()
    for path in directory.rglob('*'):
        require(not path.is_symlink(), 'Original PDF capture symlink refused')
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    require(actual == set(files), 'Original PDF capture contains missing/surplus files')
    return files


def review_original_headers(directory, source):
    """Run trusted review outside the capsule; technical failure stays visible."""
    try:
        import verify_original_report_headers as reviewer
    except ImportError:
        return {'review_completed': False, 'technical_headers_passed': False, 'productive_layout_accepted': False,
            'legal_validity_certified': False, 'limitation': 'offline_reviewer_dependency_unavailable'}
    base.tool_hash(sha(Path(reviewer.__file__).read_bytes()), 'verify_original_report_headers.py', source)
    with tempfile.TemporaryDirectory(prefix='original-report-header-review-') as folder:
        output = Path(folder).resolve()
        require(not output.is_relative_to(Path(directory).resolve()), 'Header replay output must stay outside the evidence capsule')
        try:
            result = reviewer.verify(directory, output)
        except reviewer.HeaderReviewError:
            return {'review_completed': False, 'technical_headers_passed': False, 'productive_layout_accepted': False,
                'legal_validity_certified': False, 'limitation': 'technical_header_contract_failed'}
        require(type(result['technical_headers_passed']) is bool and result['productive_layout_accepted'] is False
            and result['legal_validity_certified'] is False and len(result['repetitions']) == 3,
            'Header reviewer claimed unsupported acceptance')
        return dict(result, review_completed=True, temporary_output_outside_artifact=True,
            limitation=None if result['technical_headers_passed'] else 'technical_headers_not_preserved_on_all_pages')


def verify_original_pdf(root, receipt, *, quality_extension=False, source=None):
    """Bind actual third PDF bytes; preserve outstanding text/visual review."""
    name = 'community/original-report-pdf-evidence/proof.json'
    proof = read(root, name)
    require(type(receipt['original_report_pdf_reports']) is int and receipt['original_report_pdf_reports'] == 1
        and receipt['original_report_pdf_receipt_sha256'] == sha(safe_path(root, name).read_bytes()),
        'Operational receipt does not bind the actual third PDF proof')
    require(all(proof[key] is True for key in ('normal_actor', 'stored_history_unchanged',
        'original_action_unchanged', 'existing_structure_fk_unchanged',
        'offline_pdf_text_verification_required', 'visual_pdf_review_required'))
        and proof['original_action_numeric_adoption'] is False and proof['missing_assets'] == []
        and type(proof['pages']) is int and proof['pages'] > 0
        and type(proof['actor_id']) is int and proof['actor_id'] > 0
        and proof.get('visual_reviewed', False) is False and proof.get('pdf_text_verified', False) is False,
        'Original report PDF actor/history/action/remaining-review contract differs')
    require(isinstance(proof['file'], str) and Path(proof['file']).name == proof['file']
        and proof['file'].endswith('.pdf'), 'Original report PDF file scope differs')
    body = safe_path(root, 'community/original-report-pdf-evidence/' + proof['file']).read_bytes()
    require(body.startswith(b'%PDF-') and type(proof['bytes']) is int and proof['bytes'] == len(body) > 0
        and sha(body) == proof['sha256'], 'Actual original-report PDF bytes/hash differ')
    assets = proof['runtime_asset_sha256']
    require(isinstance(assets, dict) and assets and all(isinstance(path, str) and path.startswith('/')
        and not path.startswith('//') and isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest)
        for path, digest in assets.items())
        and isinstance(proof['financial_verified_html_sha256'], str)
        and re.fullmatch('[0-9a-f]{64}', proof['financial_verified_html_sha256']),
        'Original report PDF runtime assets/verified HTML evidence differs')
    result = {'actual_pdf_count': 1, 'bytes': len(body), 'pages': proof['pages'], 'sha256': sha(body),
        'original_action_numeric_adoption': False, 'text_verification_required': True, 'visual_review_required': True}
    if quality_extension:
        directory = safe_path(root, 'community/original-report-pdf-evidence')
        files = original_pdf_inventory(directory, repeated=True)
        result.update(actual_pdf_count=3, logical_report_count=1, repetitions=3,
            capture_files={name: {'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size} for name, path in files.items()},
            header_review=review_original_headers(directory, source), productive_layout_accepted=False,
            legal_validity_certified=False)
        assets = read(directory, 'assets.json')
        result['asset_capture'] = {'receipt_sha256': proof['asset_capture']['sha256'], 'urls': len(assets),
            'deduplicated_files': len({entry['file'] for entry in assets.values()}),
            'all_runtime_urls_and_bytes_exact': True, 'python_source_files_in_asset_cache': False,
            'session_headers_or_cookies_captured': False,
            'causal_rerender_executed': False}
    return result


def verify_receipt(root, source, packet, mode, *, operational_extensions=False, quality_extension=False, critical_extension=False, critical_generation='R3'):
    receipt = read(root, mode + '/passed.json')
    expected = expected_tests(operational_extensions, quality_extension, critical_extension, critical_generation)[mode]
    installation.check_generation(receipt, critical_extension, critical_generation)
    require(receipt.get('critical_extension', False) is critical_extension, 'Exact critical receipt/profile flag required')
    require(receipt.get('operational_extensions', False) is operational_extensions
        and receipt.get('quality_extension', False) is quality_extension, 'MF operational extension receipt/profile differs')
    if quality_extension:
        require(receipt['quality_vendor_revision'] == quality_vendor.PIN, 'Exact quality provider revision required')
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
    methods = critical_methods(source, log, mode, operational_extensions=operational_extensions, quality_extension=quality_extension, critical_extension=critical_extension, critical_generation=critical_generation)
    installed_proof = read(root, mode + '/module-installation.json')
    base.tool_hash(installed_proof['tool_sha256'], 'audit_multifront_installation.py', source)
    require(tuple(installation.owned_modules(operational_extensions, quality_extension)) == own_modules(operational_extensions, quality_extension), 'Installation postflight packet scope differs')
    installation_summary = installation.verify(installed_proof, mode, source, receipt, operational_extensions=operational_extensions, quality_extension=quality_extension, critical_extension=critical_extension, critical_generation=critical_generation)
    finance = read(root, mode + '/finance-frontier.json')
    alias_audit = expected_alias_contract(finance['aliases'])
    finance_modules = ('step_account_balance_analytic', 'step_bank_export_core', 'step_accounting_multicurrency_core')
    if mode != 'community':
        finance_modules += ('step_account_treasury_batch', 'step_bank_security', 'step_accounting_multicurrency')
    versions = {module: ast.literal_eval(source[module + '/__manifest__.py'].decode('utf-8-sig'))['version'] for module in finance_modules}
    require(finance['mode'] == ('community' if mode == 'community' else 'cerro-copy')
            and finance['versions'] == versions
            and len(finance['multicurrency_legacy_aliases']) == 37
            and finance['draft_grouping_provider'] is True and finance['payment_formats_use_original_model'] is True
            and finance['batch_conversion_certified'] is False and finance['writes_to_source'] is False,
            'MF actual finance registry evidence differs')
    require(finance.get('draft_manual_payment_posting', False) is operational_extensions,
            'Actual finance registry posting profile differs')
    require(finance.get('draft_linked_invoice_application', False) is critical_extension,
            'Critical linked-invoice accounting profile differs')
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
    summary = {'tests': expected, 'critical_multifront_methods': methods,
               'module_installation': installation_summary, 'banking_alias_contract': alias_audit, **receipt['counts']}
    if operational_extensions:
        if mode == 'community':
            summary['original_report_pdf'] = verify_original_pdf(root, receipt, quality_extension=quality_extension, source=source)
        else:
            require(type(receipt['original_report_pdf_reports']) is int and receipt['original_report_pdf_reports'] == 0
                and receipt['original_report_pdf_receipt_sha256'] is None
                and not (root / 'cerro-reference/original-report-pdf-evidence').exists(),
                'Native original report must remain a no-op, without a new PDF/adoption')
    return receipt, summary


def verify_preservation(root, source, native, repo, *, operational_extensions=False, quality_extension=False, critical_extension=False, critical_generation='R3'):
    admission = read(root, 'cerro-reference/version-admission.json')
    require(admission, 'MF native upgrade version admission is missing')
    for module, row in admission.items():
        require(module in own_modules(operational_extensions, quality_extension) and row['downgrade'] is False
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
        installation.check_generation(proof, critical_extension, critical_generation)
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


def verify_vendor(root):
    directory = safe_path(root, 'oca-vendor')
    require(directory.is_dir(), 'Operational OCA vendor sources missing')
    for module, version in vendor.VERSIONS.items():
        manifest = ast.literal_eval(safe_path(root, 'oca-vendor/' + module + '/__manifest__.py').read_text(encoding='utf-8-sig'))
        require(manifest['license'] == 'LGPL-3' and manifest['version'] == version, 'Nonfree/unpinned vendor refused before runtime bodies')
    files = {}
    for path in directory.rglob('*'):
        require(not path.is_symlink(), 'Vendor source symlink refused')
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = path.read_bytes()
    result = vendor.verify(read(root, 'oca-vendor-git-proof.json'), files)
    require(sum(result['module_files'].values()) == len(files) == 266, 'Exact 266-file operational payroll vendor tree required')
    require(read(root, 'community/vendor-files.json') == {name: sha(body) for name, body in files.items()},
        'Executed operational vendor source inventory differs from pinned Git')
    original = previous.engine_snapshot(root, 'engine-original')
    require({name.removeprefix('payroll/'): body for name, body in files.items() if name.startswith('payroll/')} == original,
        'Vendor payroll source differs from the separately proven 144-file engine')
    return result


def verify_quality_vendor(root):
    """Keep the AGPL Quality tree independent from the LGPL payroll vendor."""
    directory = safe_path(root, 'quality-vendor')
    require(directory.is_dir(), 'Quality vendor sources missing')
    manifest = ast.literal_eval(safe_path(root, 'quality-vendor/' + quality_vendor.MODULE + '/__manifest__.py').read_text(encoding='utf-8-sig'))
    require(manifest['license'] == quality_vendor.LICENSE and manifest['version'] == quality_vendor.VERSION
        and manifest['depends'] == quality_vendor.DEPENDENCIES, 'Nonfree/unpinned Quality provider refused before runtime bodies')
    files = {}
    for path in directory.rglob('*'):
        require(not path.is_symlink(), 'Quality vendor symlink refused')
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = path.read_bytes()
    proof = read(root, 'quality-vendor-git-proof.json')
    result = quality_vendor.verify(proof, files)
    require(result['file_count'] == len(files) == 114 and result['oca_pin'] == installation.QUALITY_PIN
        and result['vendor_sources_unmodified'] is True and result['all_blobs_bound_to_pinned_commit'] is True,
        'Exact unmodified 114-file Quality Git tree required')
    hashes = {name: sha(body) for name, body in files.items()}
    for mode in EXPECTED_TESTS:
        require(read(root, mode + '/quality-vendor-files.json') == hashes
            and read(root, mode + '/quality-vendor-proof.json') == proof, 'Executed Quality provider/proof differs from pinned Git')
    return result


def verify(evidence, *, repo=None, operational_extensions=False, quality_extension=False, critical_extension=False, critical_generation='R3'):
    root = Path(evidence).resolve()
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parents[2]
    source = git_sources(repo, operational_extensions=operational_extensions, quality_extension=quality_extension)
    verify_file_manifest(root, operational_extensions=operational_extensions, quality_extension=quality_extension, critical_extension=critical_extension, critical_generation=critical_generation)
    verify_executed_tools(root, source, operational_extensions=operational_extensions, quality_extension=quality_extension)
    packet = verify_packets(root, source, operational_extensions=operational_extensions, quality_extension=quality_extension)
    if critical_generation == 'S':
        require(len(packet) == 513, 'S exact packet file count differs')
    # This provider is private AGPL source, not a repository addon. Its entire
    # 52-file replay was validated above before its manifest joins the trusted
    # postflight source map.
    source.update({builder.MODULE + '/' + name: body
                   for name, body in base.addon_snapshot(root, 'normal-provider').items()})
    engine = previous.verify_engine(root, source)
    require(engine['source_files'] == engine['candidate_files'] == 144, 'MF NUMERIC engine file inventory differs')
    base.verify_hr_derivation(root, source)
    vendor_summary = verify_vendor(root) if operational_extensions else None
    quality_summary = verify_quality_vendor(root) if quality_extension else None
    community, community_summary = verify_receipt(root, source, packet, 'community', operational_extensions=operational_extensions, quality_extension=quality_extension, critical_extension=critical_extension, critical_generation=critical_generation)
    native, native_summary = verify_receipt(root, source, packet, 'cerro-reference', operational_extensions=operational_extensions, quality_extension=quality_extension, critical_extension=critical_extension, critical_generation=critical_generation)
    preservation = verify_preservation(root, source, native, repo, operational_extensions=operational_extensions, quality_extension=quality_extension, critical_extension=critical_extension, critical_generation=critical_generation)
    result = {'schema': 1, 'profile': 'multifront-quality-extension' if quality_extension else 'multifront-operational-extensions' if operational_extensions else 'multifront-normal-provider', 'exact_packet_matches_git': True,
            'package_files': len(packet), 'owned_modules': len(own_modules(operational_extensions, quality_extension)), 'normal_provider_files': 52,
            'oca_numeric_engine': engine, 'community': community_summary, 'native_reference': native_summary,
            'preservation': preservation, 'inventory': verify_inventory(root, source),
            'cold_bootstrap_claimed': False, 'original_masters_imported': False, 'operational_package': False,
            'historical_conversion': False, 'financial_certified': False, 'simpledigital_certified': False,
            'deadline_resolved': False, 'artifact_code_executed': False, 'verifier_sha256': sha(Path(__file__).read_bytes())}
    if operational_extensions:
        result.update(operational_extensions=True, oca_unmodified_vendor=vendor_summary)
    if critical_extension:
        result.update(critical_extension=True, profile='multifront-critical-extension')
    if critical_generation == 'S':
        result.update(critical_generation='S', profile='multifront-critical-S-original-interface')
    if quality_extension:
        result.update(quality_extension=True, oca_unmodified_quality_vendor=quality_summary,
            quality_native_identity_converted=False, productive_layout_accepted=False, legal_validity_certified=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--operational-extensions', action='store_true')
    parser.add_argument('--quality-extension', action='store_true')
    parser.add_argument('--critical-extension', action='store_true')
    parser.add_argument('--critical-generation', choices=installation.CRITICAL_GENERATIONS, default='R3')
    args = parser.parse_args()
    result = verify(args.evidence, operational_extensions=args.operational_extensions, quality_extension=args.quality_extension, critical_extension=args.critical_extension, critical_generation=args.critical_generation)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    counts = expected_tests(args.operational_extensions, args.quality_extension, args.critical_extension, args.critical_generation)
    print('MULTIFRONT_EVIDENCE_VERIFIED: Community %s / native %s; integral conversion remains pending' % (counts['community'], counts['cerro-reference']))


if __name__ == '__main__':
    main()
