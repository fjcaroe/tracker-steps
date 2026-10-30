"""Offline policy negatives; all evidence in these tests is synthetic."""
import ast
import base64
import importlib.util
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import verify_multifront_evidence as verifier


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def packet_fixture(operational_extensions=False, quality_extension=False):
    provider = {'__manifest__.py': repr({'license': 'AGPL-3'}).encode()}
    provider.update({'synthetic_%02d.txt' % index: str(index).encode() for index in range(51)})
    source = {module + '/__manifest__.py': repr({'license': 'LGPL-3', 'version': '18.0.1.0.0'}).encode()
              for module in verifier.own_modules(operational_extensions, quality_extension)}
    source['tools/community/simpledigital_runtime_source.json'] = json.dumps(
        {'files': {name: verifier.sha(body) for name, body in provider.items()}}).encode()
    packet = {name: verifier.sha(body) for name, body in source.items() if name.split('/')[0] in verifier.own_modules(operational_extensions, quality_extension)}
    packet.update({verifier.builder.MODULE + '/' + name: verifier.sha(body) for name, body in provider.items()})
    return source, provider, packet


def quality_fixture(count=114):
    """Synthetic complete Git tree, never an OCA or product acceptance claim."""
    vendor = verifier.quality_vendor
    files = {vendor.MODULE + '/__manifest__.py': repr({'version': vendor.VERSION, 'license': vendor.LICENSE,
        'depends': vendor.DEPENDENCIES}).encode()}
    files.update({vendor.MODULE + '/fixture_%03d.txt' % index: b'synthetic inert fixture\n' for index in range(count - 1)})
    module = b''.join(b'100644 ' + name.split('/', 1)[1].encode() + b'\0' + bytes.fromhex(vendor.git_object_oid('blob', body))
        for name, body in sorted(files.items()))
    module_id = vendor.git_object_oid('tree', module)
    root = b'40000 ' + vendor.MODULE.encode() + b'\0' + bytes.fromhex(module_id)
    commit = ('tree ' + vendor.git_object_oid('tree', root) + '\n\nSynthetic vendor custody fixture\n').encode()
    pin = vendor.git_object_oid('commit', commit)
    hashes, seal = vendor.fingerprint(files)
    proof = {'schema': 1, 'repository': vendor.REPOSITORY, 'oca_pin': pin, 'module': vendor.MODULE,
        'version': vendor.VERSION, 'license': vendor.LICENSE, 'dependencies': vendor.DEPENDENCIES,
        'commit_object_b64': base64.b64encode(commit).decode(), 'root_tree_object_b64': base64.b64encode(root).decode(),
        'trees_by_oid_b64': {module_id: base64.b64encode(module).decode()}, 'source_files_sha256': hashes,
        'source_files_fingerprint': seal, 'file_count': count, 'vendor_sources_unmodified': True,
        'native_identity_converted': False, 'artifact_code_executed': False}
    return pin, proof, files


def repeated_pdf_fixture(root):
    """Byte-custody fixture only. Fake PDF bytes never certify rendering."""
    directory = root / 'community/original-report-pdf-evidence'
    directory.mkdir(parents=True)
    html = b'<html><body>Private company Chile</body></html>'
    (directory / 'preview.html').write_bytes(html)
    assets = {}
    (directory / 'assets').mkdir()
    for url, body, mime in (('/web/assets/fixture.css', b'body{}', 'text/css; charset=utf-8'),
            ('/web/assets/duplicate.css', b'body{}', 'text/css; charset=utf-8'),
            ('/web/static/fixture.woff2', b'synthetic inert font custody bytes', 'font/woff2')):
        name = 'assets/' + verifier.sha(body) + '.bin'
        (directory / name).write_bytes(body)
        assets[url] = {'file': name, 'sha256': verifier.sha(body), 'bytes': len(body), 'content_type': mime}
    write(directory, 'assets.json', assets)
    repetitions = []
    environment = {'uid': 7, 'sudo': False, 'allowed_company_ids': [9]}
    for index in range(1, 4):
        folder = directory / ('repetition-%s' % index); folder.mkdir()
        def entry(name):
            (folder / name).write_bytes(html)
            return {'file': name, 'sha256': verifier.sha(html), 'bytes': len(html)}
        prepared = {'environment': environment, 'report_model': 'hr.payslip', 'html': entry('prepare.html'),
            'bodies': [entry('prepare-body.html')], 'header': entry('prepare-header.html'), 'footer': entry('prepare-footer.html'),
            'document_ids': [41], 'specific_paperformat_args': {}, 'company_name_present': True,
            'country_name_present': True, 'embedded_images': []}
        run = {'environment': environment, 'bodies': [entry('run-body.html')], 'header': entry('run-header.html'),
            'footer': entry('run-footer.html'), 'landscape': False, 'specific_paperformat_args': {}, 'set_viewport_size': False}
        arguments = {'environment': environment, 'paperformat': [], 'landscape': False,
            'specific_paperformat_args': {}, 'set_viewport_size': False, 'arguments': ['--quiet'], 'session_arguments_captured': False}
        pipeline = {'prepare_calls': [prepared], 'run_calls': [run], 'argument_calls': [arguments]}
        write(folder, 'pipeline.json', pipeline)
        raw = (folder / 'pipeline.json').read_bytes()
        body = b'%PDF- synthetic byte fixture ' + str(index).encode()
        filename = 'fixture-%s.pdf' % index; (directory / filename).write_bytes(body)
        repetitions.append({'file': filename, 'sha256': verifier.sha(body), 'bytes': len(body), 'pages': 1,
            'pipeline': 'repetition-%s/pipeline.json' % index, 'pipeline_sha256': verifier.sha(raw), 'pipeline_bytes': len(raw),
            'prepared_headers': 1, 'wkhtmltopdf_runs': 1, 'argument_calls': 1, 'company_present_in_prepared_headers': True,
            'country_present_in_prepared_headers': True, 'normal_run_actor': True})
    proof = {key: repetitions[0][key] for key in ('file', 'sha256', 'bytes', 'pages')}
    proof.update(actor_id=7, normal_actor=True, stored_history_unchanged=True, original_action_unchanged=True,
        existing_structure_fk_unchanged=True, original_action_numeric_adoption=False, missing_assets=[],
        runtime_asset_sha256={url: entry['sha256'] for url, entry in assets.items()}, financial_verified_html_sha256=verifier.sha(html),
        offline_pdf_text_verification_required=True, visual_pdf_review_required=True, repetitions=repetitions,
        company_name='Private company', country_name='Chile', header_layout_accepted=False,
        asset_capture={'file': 'assets.json', 'sha256': verifier.sha((directory / 'assets.json').read_bytes()), 'bytes': (directory / 'assets.json').stat().st_size})
    write(directory, 'proof.json', proof)
    return directory, proof


class MultifrontEvidenceCase(unittest.TestCase):
    def test_u_225_173_methods_and_extra_helpers_are_explicit_without_changing_prior_generations(self):
        root = Path(__file__).resolve().parents[2]
        source = {path.relative_to(root).as_posix(): path.read_bytes() for module in verifier.own_modules(True, True)
            for path in (root / module).rglob('*.py')}
        keys = {cls.name + '.' + method.name for name, body in source.items() if '/tests/test_' in name
            for cls in ast.parse(body.decode('utf-8-sig')).body if isinstance(cls, ast.ClassDef)
            for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith('test_')}
        log = '\n'.join('Starting ' + key + ' ...' for key in sorted(keys))
        with patch.dict(verifier.installation.CRITICAL_GENERATIONS, U={'community': 684, 'cerro-reference': 467}):
            self.assertEqual(verifier.expected_tests(True, True, True, 'U'), {'community': 684, 'cerro-reference': 467})
            self.assertEqual(verifier.expected_tests(True, True, True, 'T'), {'community': 671, 'cerro-reference': 462})
            for mode, count, selected in (('community', 225, 'OriginalHistoryDeletionCase.'),
                    ('cerro-reference', 173, 'NativeHistoryStorageCase.')):
                self.assertEqual(verifier.critical_methods(source, log, mode, operational_extensions=True,
                    quality_extension=True, critical_extension=True, critical_generation='U'), count)
                key = next(key for key in keys if key.startswith(selected))
                with self.assertRaises(ValueError):
                    verifier.critical_methods(source, log.replace('Starting ' + key + ' ...', ''), mode,
                        operational_extensions=True, quality_extension=True, critical_extension=True, critical_generation='U')
        self.assertEqual(verifier.executed_tools('R3'), verifier.EXECUTED_TOOLS)
        self.assertEqual(verifier.executed_tools('S'), verifier.executed_tools('T'))
        self.assertEqual(set(verifier.executed_tools('U')) - set(verifier.EXECUTED_TOOLS), set(verifier.U_HELPERS))
        self.assertEqual(len(verifier.U_HELPERS), 5)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = {}
            for name in verifier.executed_tools('U'):
                raw = b'raise RuntimeError("artifact never imported")\n'
                path = root / 'executed-tools' / name; path.parent.mkdir(exist_ok=True); path.write_bytes(raw)
                source['tools/community/' + name] = raw
            (root / 'collector.py').write_bytes(b'collector')
            (root / 'postflight-tools').mkdir(); (root / 'postflight-tools/audit_multifront_installation.py').write_bytes(b'auditor')
            with patch.object(verifier.base, 'tool_hash'):
                verifier.verify_executed_tools(root, source, critical_generation='U')
                with self.assertRaises(ValueError): verifier.verify_executed_tools(root, source)
                (root / 'executed-tools' / verifier.U_HELPERS[0]).write_bytes(b'tampered')
                with self.assertRaises(ValueError): verifier.verify_executed_tools(root, source, critical_generation='U')

    def test_u_final_engine_replays_real_trusted_composition_and_keeps_numeric_intermediate_separate(self):
        import original_history_engine_contract as engine
        from test_original_history_engine_contract import fixture, pinned_fixture
        original, schema, guard = fixture()
        # The fixture uses actual checked-in own guard bytes; the coordinator's
        # independently reviewed final pin is still supplied by the engine tool.
        with pinned_fixture(original, schema), patch.object(engine, 'GUARD_SHA256',
                verifier.sha(guard[engine.GUARD_FILE].replace(b'\r\n', b'\n'))):
            candidate, report = engine.compose(original, schema, guard)
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                for prefix, files in (('engine-original/payroll', original), ('engine-candidate/payroll', candidate)):
                    for name, raw in files.items():
                        path = root / prefix / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
                (root / 'schema-plan.json').write_bytes(schema)
                write(root, engine.REPORT, report)
                write(root, verifier.numeric.REPORT, verifier.numeric.report_for(original, verifier.numeric.plan(original)))
                write(root, 'engine-git-proof.json', {'synthetic': 'separate Git proof delegation only'})
                source = dict(guard)
                source.update({'tools/community/' + name: (Path(engine.__file__).parent / name).read_bytes()
                    for name in engine.TOOLS})
                with patch.object(verifier.previous, 'verify_engine_git', return_value={'bound': True}) as git:
                    result = verifier.verify_u_engine(root, source)
                    git.assert_called_once_with({'synthetic': 'separate Git proof delegation only'}, original)
                    self.assertTrue(result['numeric_intermediate']['intermediate_only'])
                    self.assertFalse(result['numeric_intermediate']['executed_final_engine_is_numeric_only'])
                    self.assertTrue(result['final_engine']['all_stage_hashes_recomputed'])
                    self.assertEqual(result['final_engine']['files'], 144)
                    path = root / 'engine-candidate/payroll' / engine.deletion.FILE
                    path.write_bytes(verifier.numeric.plan(original)[engine.deletion.FILE])
                    with self.assertRaises(ValueError): verifier.verify_u_engine(root, source)
                    path.write_bytes(candidate[engine.deletion.FILE])
                    altered = verifier.numeric.report_for(original, verifier.numeric.plan(original))
                    altered['candidate_files'] = verifier.numeric.hashes(candidate)
                    altered.pop('seal_sha256'); altered['seal_sha256'] = verifier.numeric.seal(altered)
                    write(root, verifier.numeric.REPORT, altered)
                    with self.assertRaises(ValueError): verifier.verify_u_engine(root, source)

    def test_u_first_load_gate_and_four_real_catalog_contracts_bind_chronology_without_waivers(self):
        import audit_payroll_history_storage as audit
        import preflight_original_history_storage as before_gate
        from test_audit_payroll_history_storage import fixture as catalog_fixture
        from test_preflight_original_history_storage import snapshot, database, Callback
        import original_history_engine_contract as engine
        for mode in ('community', 'cerro-reference'):
            pre_mode = 'cold-community' if mode == 'community' else 'native'
            db = database(pre_mode)
            before = before_gate.capture(Callback(snapshot(pre_mode, absent=mode == 'community')), db, pre_mode)
            catalog = catalog_fixture()
            catalog['transaction'] = [{'database': db, 'read_only': 'on', 'default_read_only': 'on', 'isolation': 'repeatable read'}]
            catalog['providers'] = [{'name': 'payroll' if mode == 'community' else 'hr_payroll',
                'license': 'LGPL-3' if mode == 'community' else 'OEEL-1', 'latest_version': '18.0.1.4.0'}]
            if mode == 'community':
                catalog['providers'].append({'name': 'step_payroll_oca_api', 'license': 'LGPL-3', 'latest_version': '18.0.1.17.0'})
            runtime = {'schema': 1, 'database': db, 'read_only': True, 'registry_loaded_by_caller': True,
                'records_read': False, 'computes_evaluated': False, 'database_writes': False, 'fields': [
                    {'model': model, 'table': table, 'name': name, 'type': 'many2one' if kind == 'int4' else 'char',
                        'required': required, 'translate': translate, 'store': True, 'column_type': [kind, kind],
                        'ondelete': 'set null' if kind == 'int4' else None,
                        'comodel_name': 'resource.calendar' if kind == 'int4' else None}
                    for model, table, name, kind, required, translate in audit.SPECS]}
            after = {'schema': 1, 'database': db, 'profile': 'normal-community' if mode == 'community' else 'native-reference',
                'tool_sha256': verifier.sha(Path(audit.__file__).read_bytes()), 'read_only': True, 'database_writes': False,
                'historical_rows_assessed': False, 'metadata_before': catalog, 'metadata_after': deepcopy(catalog),
                'runtime': runtime, 'assessment': audit.assess(catalog, runtime)}
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                write(root, mode + '/before-initialization-storage.json', before)
                write(root, engine.REPORT, {'synthetic': 'receipt hash only, engine tested separately'})
                receipt = {'database': db, 'counts': {'installed': len(catalog['providers']), 'enterprise': 0 if mode == 'community' else 1},
                    'before_initialization_storage_sha256': verifier.sha((root / mode / 'before-initialization-storage.json').read_bytes()),
                    'history_engine_derivation_sha256': verifier.sha((root / engine.REPORT).read_bytes()) if mode == 'community' else None}
                receipt['before_initialization_chronology'] = {'database': db,
                    'preflight_sha256': receipt['before_initialization_storage_sha256'], 'preflight_completed_before_initializer': True,
                    'shared_environment_lease': True, 'initializer_source': 'candidate-first-init'}
                source = {'tools/community/audit_payroll_history_storage.py': Path(audit.__file__).read_bytes()}
                for change in (None, 'chronology', 'lease', 'preflight_sha', 'report_scope', 'jsonb_line',
                        'runtime_sudo_read', 'runtime_type', 'catalog_drift', 'waiver', 'provider', 'tool'):
                    actual, captured = deepcopy(receipt), deepcopy(after)
                    if change == 'chronology': actual['before_initialization_chronology']['preflight_completed_before_initializer'] = False
                    if change == 'lease': actual['before_initialization_chronology']['shared_environment_lease'] = False
                    if change == 'preflight_sha': actual['before_initialization_storage_sha256'] = '0' * 64
                    if change == 'report_scope': actual['history_engine_derivation_sha256'] = None if mode == 'community' else '0' * 64
                    if change == 'jsonb_line':
                        for data in (captured['metadata_before'], captured['metadata_after']): data['columns'][0]['typname'] = 'jsonb'
                    if change == 'runtime_sudo_read': captured['runtime']['records_read'] = True
                    if change == 'runtime_type': captured['runtime']['fields'][0]['column_type'] = ['jsonb', 'jsonb']
                    if change == 'catalog_drift': captured['metadata_after']['fields'][0]['id'] += 99
                    if change == 'waiver': captured['assessment']['other_columns_waived'] = ['name']
                    if change == 'provider': captured['metadata_before']['providers'][0]['name'] = 'other_engine'
                    if change == 'tool': captured['tool_sha256'] = '0' * 64
                    write(root, mode + '/after-tests-history-storage.json', captured)
                    actual['history_storage_after_sha256'] = verifier.sha((root / mode / 'after-tests-history-storage.json').read_bytes())
                    if change is None:
                        result = verifier.verify_u_storage_boundary(root, source, actual, mode)
                        self.assertTrue(result['chronology_bound_by_root_receipt'])
                        self.assertEqual(result['after_tests_four_contracts']['catalog_contracts_closed'], 4)
                        self.assertFalse(result['historical_rows_assessed'])
                    else:
                        with self.subTest(mode=mode, change=change), self.assertRaises(ValueError):
                            verifier.verify_u_storage_boundary(root, source, actual, mode)

    def test_quality_profile_is_exact_thirtythree_and_never_an_implicit_operational_extension(self):
        source, provider, packet = packet_fixture(True, True)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for prefix in ('original-provider', 'normal-provider'):
                path = root / prefix / '__manifest__.py'; path.parent.mkdir(); path.write_bytes(provider['__manifest__.py'])
            for mode in verifier.EXPECTED_TESTS: write(root, mode + '/source-files.json', packet)
            with patch.object(verifier.previous.base, 'addon_snapshot', return_value=provider), \
                    patch.object(verifier.previous, 'replay_normal_provider', return_value=provider):
                self.assertEqual(verifier.verify_packets(root, source, operational_extensions=True, quality_extension=True), packet)
                with self.assertRaises(verifier.base.EvidenceError): verifier.verify_packets(root, source, operational_extensions=True)
                for name in ('step_quality_contracts', 'step_quality_oca', 'step_qa_native_reference'):
                    altered = dict(packet); altered.pop(name + '/__manifest__.py')
                    for mode in verifier.EXPECTED_TESTS: write(root, mode + '/source-files.json', altered)
                    with self.assertRaises(verifier.base.EvidenceError):
                        verifier.verify_packets(root, source, operational_extensions=True, quality_extension=True)
        for operational, quality in ((False, True), (1, True), (True, 1)):
            with self.assertRaises(verifier.base.EvidenceError): verifier.expected_tests(operational, quality)
        self.assertEqual(verifier.expected_tests(True, True), {'community': 646, 'cerro-reference': 441})

    def test_s_212_168_methods_require_every_mode_specific_test_once(self):
        root = Path(__file__).resolve().parents[2]
        source = {path.relative_to(root).as_posix(): path.read_bytes() for module in verifier.own_modules(True, True)
            for path in (root / module).rglob('*.py')}
        keys = {cls.name + '.' + method.name for name, body in source.items() if '/tests/test_' in name
            for cls in ast.parse(body.decode('utf-8-sig')).body if isinstance(cls, ast.ClassDef)
            for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith('test_')}
        log = '\n'.join('Starting ' + key + ' ...' for key in sorted(keys))
        for mode, expected, selected in (('community', 212, 'QualityOcaOperationCase.'), ('cerro-reference', 168, 'NativeQualityConsumerCase.')):
            self.assertEqual(verifier.critical_methods(source, log, mode, operational_extensions=True, quality_extension=True, critical_extension=True, critical_generation='S'), expected)
            key = next(key for key in keys if key.startswith(selected))
            for changed in (log.replace('Starting ' + key + ' ...', ''), log + '\nStarting ' + key + ' ...'):
                with self.subTest(mode=mode), self.assertRaises(verifier.base.EvidenceError):
                    verifier.critical_methods(source, changed, mode, operational_extensions=True, quality_extension=True, critical_extension=True, critical_generation='S')

    def test_s_and_r3_manifest_generations_are_explicit_and_disjoint(self):
        self.assertEqual(verifier.expected_tests(True, True, True), {'community': 665, 'cerro-reference': 457})
        self.assertEqual(verifier.expected_tests(True, True, True, 'S'), {'community': 671, 'cerro-reference': 462})
        with self.assertRaises(ValueError): verifier.expected_tests(True, True, False, 'S')
        for generation in ('R3', 'S'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                manifest = {'schema': 1, 'files': {}, 'database_accessed': False, 'database_writes': False,
                    'dump_exported': False, 'enterprise_source_bodies_exported': False,
                    'operational_extensions': True, 'quality_extension': True, 'critical_extension': True}
                if generation == 'S': manifest['critical_generation'] = 'S'
                write(root, 'evidence-files.json', manifest)
                verifier.verify_file_manifest(root, operational_extensions=True, quality_extension=True,
                    critical_extension=True, critical_generation=generation)
                with self.assertRaises(ValueError):
                    verifier.verify_file_manifest(root, operational_extensions=True, quality_extension=True,
                        critical_extension=True, critical_generation='S' if generation == 'R3' else 'R3')

    def test_quality_vendor_binds_all_114_git_blobs_and_both_executed_inventories(self):
        for change in (None, 'partial_valid_tree', 'blob', 'extra', 'native_inventory', 'native_proof', 'license'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                pin, proof, files = quality_fixture(113 if change == 'partial_valid_tree' else 114)
                for name, body in files.items():
                    path = root / 'quality-vendor' / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
                write(root, 'quality-vendor-git-proof.json', proof)
                for mode in verifier.EXPECTED_TESTS:
                    write(root, mode + '/quality-vendor-proof.json', proof)
                    write(root, mode + '/quality-vendor-files.json', {name: verifier.sha(body) for name, body in files.items()})
                if change == 'blob': (root / 'quality-vendor' / next(name for name in files if name.endswith('.txt'))).write_bytes(b'tampered')
                elif change == 'extra': (root / 'quality-vendor/quality_control_oca/unreviewed.py').write_text('raise RuntimeError("never execute")')
                elif change == 'native_inventory': write(root, 'cerro-reference/quality-vendor-files.json', {})
                elif change == 'native_proof': write(root, 'cerro-reference/quality-vendor-proof.json', dict(proof, artifact_code_executed=True))
                elif change == 'license': (root / 'quality-vendor/quality_control_oca/__manifest__.py').write_text(repr({'license': 'OEEL-1'}))
                with patch.object(verifier.quality_vendor, 'PIN', pin), patch.object(verifier.installation, 'QUALITY_PIN', pin):
                    if change is None:
                        result = verifier.verify_quality_vendor(root)
                        self.assertEqual(result['file_count'], 114)
                        self.assertFalse(result['native_identity_converted'])
                    else:
                        with self.subTest(change=change), self.assertRaises((ValueError, KeyError)):
                            verifier.verify_quality_vendor(root)

    def test_three_pdf_capture_seals_actual_pipeline_inputs_without_accepting_header_claims(self):
        for change in (None, 'missing_repeat', 'duplicate_pdf', 'pipeline_bytes', 'preview', 'tampered_header',
                'cookie_arg', 'cookie_key', 'sudo', 'path', 'extra_code', 'header_claim'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder); directory, proof = repeated_pdf_fixture(root)
                pipeline_path = directory / proof['repetitions'][0]['pipeline']
                pipeline = json.loads(pipeline_path.read_text())
                if change == 'missing_repeat': proof['repetitions'].pop()
                elif change == 'duplicate_pdf': proof['repetitions'][1]['file'] = proof['repetitions'][0]['file']
                elif change == 'pipeline_bytes': proof['repetitions'][0]['pipeline_bytes'] += 1
                elif change == 'preview': (directory / 'preview.html').write_bytes(b'changed')
                elif change == 'tampered_header': (directory / 'repetition-1/run-header.html').write_bytes(b'changed')
                elif change == 'cookie_arg': pipeline['argument_calls'][0]['arguments'] += ['--cookie', 'private-session', 'never-export']
                elif change == 'cookie_key': pipeline['run_calls'][0]['cookie'] = 'never-export'
                elif change == 'sudo': pipeline['run_calls'][0]['environment']['sudo'] = True
                elif change == 'path': proof['repetitions'][0]['pipeline'] = '../outside/pipeline.json'
                elif change == 'extra_code': (directory / 'artifact.py').write_text('raise RuntimeError("must stay inert")')
                elif change == 'header_claim': proof['header_layout_accepted'] = True
                if change in ('cookie_arg', 'cookie_key', 'sudo'):
                    pipeline_path.write_text(json.dumps(pipeline))
                    proof['repetitions'][0].update(pipeline_sha256=verifier.sha(pipeline_path.read_bytes()), pipeline_bytes=pipeline_path.stat().st_size)
                write(directory, 'proof.json', proof)
                receipt = {'original_report_pdf_reports': 1,
                    'original_report_pdf_receipt_sha256': verifier.sha((directory / 'proof.json').read_bytes())}
                review = {'review_completed': True, 'technical_headers_passed': False, 'productive_layout_accepted': False,
                    'legal_validity_certified': False, 'limitation': 'technical_headers_not_preserved_on_all_pages'}
                with patch.object(verifier, 'review_original_headers', return_value=review) as reviewer:
                    if change is None:
                        result = verifier.verify_original_pdf(root, receipt, quality_extension=True, source={})
                        self.assertEqual(result['actual_pdf_count'], 3)
                        self.assertEqual(len(result['capture_files']), 32)
                        self.assertEqual(result['asset_capture']['urls'], 3)
                        self.assertEqual(result['asset_capture']['deduplicated_files'], 2)
                        self.assertFalse(result['asset_capture']['causal_rerender_executed'])
                        self.assertFalse(result['header_review']['technical_headers_passed'])
                        self.assertFalse(result['legal_validity_certified'])
                        self.assertEqual(len(verifier.original_pdf_inventory(directory, repeated=True)), 32)
                        reviewer.assert_called_once()
                    else:
                        with self.subTest(change=change), self.assertRaises(verifier.base.EvidenceError):
                            verifier.verify_original_pdf(root, receipt, quality_extension=True, source={})
                        reviewer.assert_not_called()

    def test_quality_asset_cache_requires_hash_bound_map_exact_dedup_and_no_source_or_session_material(self):
        for change in ('missing_receipt', 'map_hash', 'changed_bytes', 'missing_bytes', 'boolean_length', 'extra_binary',
                'extra_cookie_file', 'source_url', 'encoded_source_url', 'cookie_key', 'python_mime', 'header_injection',
                'duplicate_url', 'runtime_set', 'wrong_cache_path'):
            with tempfile.TemporaryDirectory() as folder:
                directory, proof = repeated_pdf_fixture(Path(folder))
                asset_path = directory / 'assets.json'; assets = json.loads(asset_path.read_text())
                url = next(iter(assets)); entry = assets[url]
                if change == 'missing_receipt': proof.pop('asset_capture')
                elif change == 'map_hash': proof['asset_capture']['sha256'] = '0' * 64
                elif change == 'changed_bytes': (directory / entry['file']).write_bytes(b'tampered')
                elif change == 'missing_bytes': (directory / entry['file']).unlink()
                elif change == 'boolean_length': entry['bytes'] = True
                elif change == 'extra_binary': (directory / 'assets' / ('0' * 64 + '.bin')).write_bytes(b'not in runtime cache')
                elif change == 'extra_cookie_file': (directory / 'assets/cookies.json').write_text('{}')
                elif change in ('source_url', 'encoded_source_url'):
                    renamed = '/web/static/source.py' if change == 'source_url' else '/web/static/source%2epy'
                    assets[renamed] = assets.pop(url)
                    proof['runtime_asset_sha256'][renamed] = proof['runtime_asset_sha256'].pop(url)
                elif change == 'cookie_key': entry['cookie'] = 'synthetic-session-material-must-be-refused'
                elif change == 'python_mime': entry['content_type'] = 'text/x-python'
                elif change == 'header_injection': entry['content_type'] = 'text/css;\r\ncharset=utf-8'
                elif change == 'runtime_set': proof['runtime_asset_sha256']['/not-captured'] = '0' * 64
                elif change == 'wrong_cache_path': entry['file'] = 'assets/source.py'
                if change not in ('missing_receipt', 'map_hash'):
                    raw = json.dumps(assets).encode()
                    if change == 'duplicate_url':
                        raw = ('{' + ','.join(json.dumps(key) + ':' + json.dumps(value) for key, value in assets.items())
                            + ',' + json.dumps(url) + ':' + json.dumps(entry) + '}').encode()
                    asset_path.write_bytes(raw)
                    proof['asset_capture'].update(sha256=verifier.sha(raw), bytes=len(raw))
                write(directory, 'proof.json', proof)
                with self.subTest(change=change), self.assertRaises(verifier.base.EvidenceError):
                    verifier.original_pdf_inventory(directory, repeated=True)

    @unittest.skipUnless(importlib.util.find_spec('pymupdf') and importlib.util.find_spec('lxml'), 'Optional offline PDF review dependencies')
    def test_real_offline_header_failure_does_not_mutate_capture_or_become_layout_acceptance(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); directory, proof = repeated_pdf_fixture(root)
            # A real PDF engine creates this explicit unit fixture. It is not
            # an Odoo result, and its absent header must remain a limitation.
            with pymupdf.open() as document:
                page = document.new_page(); page.insert_text((72, 72), 'Synthetic unit fixture; no company header or logo')
                pdf = document.tobytes()
            for repetition in proof['repetitions']:
                (directory / repetition['file']).write_bytes(pdf)
                repetition.update(sha256=verifier.sha(pdf), bytes=len(pdf))
            proof.update({key: proof['repetitions'][0][key] for key in ('file', 'sha256', 'bytes', 'pages')})
            write(directory, 'proof.json', proof)
            before = {path.relative_to(directory).as_posix(): path.read_bytes() for path in directory.rglob('*') if path.is_file()}
            receipt = {'original_report_pdf_reports': 1, 'original_report_pdf_receipt_sha256': verifier.sha((directory / 'proof.json').read_bytes())}
            helper = Path(verifier.__file__).with_name('verify_original_report_headers.py')
            result = verifier.verify_original_pdf(root, receipt, quality_extension=True,
                source={'tools/community/verify_original_report_headers.py': helper.read_bytes()})
            self.assertTrue(result['header_review']['review_completed'])
            self.assertFalse(result['header_review']['technical_headers_passed'])
            self.assertFalse(result['productive_layout_accepted'])
            self.assertFalse(result['legal_validity_certified'])
            self.assertTrue(result['header_review']['temporary_output_outside_artifact'])
            self.assertEqual(before, {path.relative_to(directory).as_posix(): path.read_bytes() for path in directory.rglob('*') if path.is_file()})

    def test_operational_packet_is_exact_thirty_with_normal_fiftytwo_and_not_quality(self):
        source, provider, packet = packet_fixture(True)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for prefix in ('original-provider', 'normal-provider'):
                path = root / prefix / '__manifest__.py'
                path.parent.mkdir(); path.write_bytes(provider['__manifest__.py'])
            for mode in verifier.EXPECTED_TESTS:
                write(root, mode + '/source-files.json', packet)
            with patch.object(verifier.previous.base, 'addon_snapshot', return_value=provider), \
                    patch.object(verifier.previous, 'replay_normal_provider', return_value=provider):
                self.assertEqual(verifier.verify_packets(root, source, operational_extensions=True), packet)
                with self.assertRaises(verifier.base.EvidenceError):
                    verifier.verify_packets(root, source)
                for edit in ('missing_reference', 'quality', 'vendor_in_own_packet', 'hash'):
                    changed = dict(packet)
                    if edit == 'missing_reference': changed.pop('step_payroll_benefits_native_reference/__manifest__.py')
                    elif edit == 'quality': changed['step_quality/__manifest__.py'] = '0' * 64
                    elif edit == 'vendor_in_own_packet': changed['payroll_contract_advantages/__manifest__.py'] = '0' * 64
                    else: changed['step_payroll_original_report/__manifest__.py'] = '0' * 64
                    for mode in verifier.EXPECTED_TESTS:
                        write(root, mode + '/source-files.json', changed)
                    with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                        verifier.verify_packets(root, source, operational_extensions=True)

    def test_actual_third_pdf_bytes_and_remaining_review_cannot_be_fabricated_as_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name = 'community/original-report-pdf-evidence/proof.json'
            body = b'%PDF- synthetic byte-custody fixture only, not a rendered product PDF'
            path = root / 'community/original-report-pdf-evidence/synthetic.pdf'
            path.parent.mkdir(parents=True); path.write_bytes(body)
            proof = {'file': 'synthetic.pdf', 'sha256': verifier.sha(body), 'bytes': len(body), 'pages': 1,
                'actor_id': 1, 'normal_actor': True, 'stored_history_unchanged': True, 'original_action_unchanged': True,
                'existing_structure_fk_unchanged': True, 'missing_assets': [], 'original_action_numeric_adoption': False,
                'runtime_asset_sha256': {'/web/assets/synthetic.css': '0' * 64}, 'financial_verified_html_sha256': '1' * 64,
                'offline_pdf_text_verification_required': True, 'visual_pdf_review_required': True}
            for edit in (None, 'bytes', 'sha', 'history', 'adoption', 'asset', 'review', 'receipt', 'actor'):
                changed = deepcopy(proof)
                if edit == 'bytes': changed['bytes'] += 1
                elif edit == 'sha': changed['sha256'] = '0' * 64
                elif edit == 'history': changed['stored_history_unchanged'] = False
                elif edit == 'adoption': changed['original_action_numeric_adoption'] = True
                elif edit == 'asset': changed['runtime_asset_sha256'] = {}
                elif edit == 'review': changed['visual_reviewed'] = True
                elif edit == 'actor': changed['actor_id'] = True
                write(root, name, changed)
                receipt = {'original_report_pdf_reports': 1,
                    'original_report_pdf_receipt_sha256': verifier.sha((root / name).read_bytes())}
                if edit == 'receipt': receipt['original_report_pdf_receipt_sha256'] = '0' * 64
                if edit is None:
                    self.assertTrue(verifier.verify_original_pdf(root, receipt)['visual_review_required'])
                else:
                    with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                        verifier.verify_original_pdf(root, receipt)

    def test_complete_manual_setup_alias_set_rejects_missing_related_or_wrong_references(self):
        from finance_frontier_contract import LEGACY_XMLIDS
        aliases = {module + '.' + name: 100 + index for index, (module, name) in enumerate(
            (module, name) for module, names in LEGACY_XMLIDS.items() for name in names)}
        for module in LEGACY_XMLIDS:
            aliases[module + '.model_res_partner_bank'] = 9
        self.assertEqual(verifier.expected_alias_contract(aliases), {'exact_legacy_aliases': 15,
            'manual_setup_related_field_aliases': 2, 'shared_bank_model_reference_exact': True})
        related = next(name for name in aliases if '.field_account_setup_bank_manual_config__' in name)
        for edit in ('missing_related', 'wrong_related_name', 'wrong_model_ref', 'duplicate_field_ref', 'bool_ref', 'extra'):
            changed = dict(aliases)
            if edit == 'missing_related': changed.pop(related)
            elif edit == 'wrong_related_name': changed[related.replace('manual_config__', 'wrong_config__')] = changed.pop(related)
            elif edit == 'wrong_model_ref': changed[next(iter(LEGACY_XMLIDS)) + '.model_res_partner_bank'] = 999
            elif edit == 'duplicate_field_ref': changed[related] = changed[next(name for name in changed if '.field_res_partner_bank__' in name)]
            elif edit == 'bool_ref': changed[related] = True
            else: changed['unexpected_namespace.original_model'] = 9
            with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                verifier.expected_alias_contract(changed)

    def test_exact_27_and_normal_52_packet_rejects_cold_missing_extra_and_hash_drift(self):
        source, provider, packet = packet_fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for provider_folder in ('original-provider', 'normal-provider'):
                path = root / provider_folder / '__manifest__.py'
                path.parent.mkdir(parents=True)
                path.write_bytes(provider['__manifest__.py'])
            for mode in verifier.EXPECTED_TESTS:
                write(root, mode + '/source-files.json', packet)
            with patch.object(verifier.previous.base, 'addon_snapshot', return_value=provider), \
                    patch.object(verifier.previous, 'replay_normal_provider', return_value=provider):
                self.assertEqual(verifier.verify_packets(root, source), packet)
                for edit in ('missing', 'extra', 'hash', 'native'):
                    changed = deepcopy(packet)
                    if edit == 'missing': changed.pop(next(iter(changed)))
                    elif edit == 'extra': changed['unreviewed_addon/__manifest__.py'] = 'f' * 64
                    else: changed[next(iter(changed))] = 'f' * 64
                    for mode in verifier.EXPECTED_TESTS:
                        write(root, mode + '/source-files.json', changed if edit != 'native' or mode == 'cerro-reference' else packet)
                    with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                        verifier.verify_packets(root, source)
                for mode in verifier.EXPECTED_TESTS:
                    write(root, mode + '/source-files.json', packet)
            cold = dict(list(provider.items())[:49])
            with patch.object(verifier.previous.base, 'addon_snapshot', return_value=cold):
                with self.assertRaisesRegex(verifier.base.EvidenceError, '52-file'):
                    verifier.verify_packets(root, source)

    def test_103_97_new_functional_methods_must_run_exactly_once(self):
        root = Path(__file__).resolve().parents[2]
        source = {path.relative_to(root).as_posix(): path.read_bytes() for module in verifier.OWN_MODULES
                  for path in (root / module).rglob('*.py')}
        for mode, expected in (('community', 103), ('cerro-reference', 97)):
            modules = verifier.NEW_MODULES if mode == 'community' else verifier.NEW_MODULES[:-1]
            keys = []
            for name, body in source.items():
                if '/tests/test_' not in name:
                    continue
                for cls in ast.parse(body.decode('utf-8-sig')).body:
                    if not isinstance(cls, ast.ClassDef):
                        continue
                    admitted = name.split('/')[0] in modules or cls.name == 'TestTEDCore' or cls.name == (
                        'TestTEDCustodyStorage' if mode == 'community' else 'TestTEDNativeCAFCustody')
                    if admitted:
                        keys += [cls.name + '.' + method.name for method in cls.body
                            if isinstance(method, ast.FunctionDef) and method.name.startswith('test_')]
            self.assertEqual(len(keys), expected)
            log = '\n'.join('Starting ' + key + ' ...' for key in keys)
            self.assertEqual(verifier.critical_methods(source, log, mode), expected)
            for changed in (log.replace('Starting ' + keys[0] + ' ...', ''), log + '\nStarting ' + keys[0] + ' ...'):
                with self.assertRaises(verifier.base.EvidenceError):
                    verifier.critical_methods(source, changed, mode)

    def test_capsule_manifest_detects_changed_missing_and_surplus_members(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            body = b'private synthetic metadata only'
            (root / 'metadata.json').write_bytes(body)
            receipt = {'schema': 1, 'files': {'metadata.json': verifier.sha(body)}, 'database_accessed': False,
                'database_writes': False, 'dump_exported': False, 'enterprise_source_bodies_exported': False}
            write(root, 'evidence-files.json', receipt)
            verifier.verify_file_manifest(root)
            for edit in ('changed', 'missing', 'extra', 'scope'):
                (root / 'metadata.json').write_bytes(body)
                (root / 'extra.py').unlink(missing_ok=True)
                write(root, 'evidence-files.json', receipt)
                if edit == 'changed': (root / 'metadata.json').write_bytes(b'different')
                elif edit == 'missing': (root / 'metadata.json').unlink()
                elif edit == 'extra': (root / 'extra.py').write_text('raise RuntimeError("must never execute")')
                else: write(root, 'evidence-files.json', dict(receipt, database_writes=True))
                with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                    verifier.verify_file_manifest(root)

    def test_original_counters_and_nonstock_business_change_fail_before_any_normalizer(self):
        before = {'business_%04d' % index: {'rows': 1, 'hash': str(index)} for index in range(921)}
        before.update({'ir_sequence_%04d' % index: {'rows': 1, 'hash': '{"last_value":1}'} for index in range(140)})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, 'cerro-reference/business-before.json', before)
            module = verifier.OWN_MODULES[0]
            source = {module + '/__manifest__.py': repr({'version': '18.0.1.0.0'}).encode()}
            write(root, 'cerro-reference/version-admission.json', {module: {
                'original': '18.0.1.0.0', 'candidate': '18.0.1.0.0', 'downgrade': False}})
            for edit in ('counter', 'business', 'new_table'):
                after = deepcopy(before)
                if edit == 'counter': after['ir_sequence_0000']['hash'] = '{"last_value":2}'
                elif edit == 'business': after['business_0000']['hash'] = 'changed'
                else: after['extra_table'] = {'rows': 0, 'hash': ''}
                write(root, 'cerro-reference/business-after-upgrade.json', after)
                write(root, 'cerro-reference/business-after.json', after)
                with patch.object(verifier.treasury, 'verify') as normalizer:
                    with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                        verifier.verify_preservation(root, source, {}, Path(folder))
                    normalizer.assert_not_called()

    def test_focused_old_count_or_unmeasured_module_graph_is_not_acceptance(self):
        receipt = {'mode': 'community', 'profile': 'simpledigital', 'accelerated': True,
            'custody_grouping': True, 'multifront': True, 'focused_development_pass': False,
            'expected_test_count': 576, 'package_files': 0, 'counts': {'installed': 123, 'enterprise': 0}}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write(root, 'community/source-files.json', {})
            receipt['source_files_sha256'] = verifier.sha((root / 'community/source-files.json').read_bytes())
            graph = {'source': 'independently_measured_by_coordinator', 'community': {'installed': 123, 'enterprise': 0}}
            write(root, 'graph-admission.json', graph)
            for edit in ('focused', 'old_tests', 'cold_tests', 'wrong_graph', 'unmeasured_graph'):
                changed = deepcopy(receipt)
                write(root, 'graph-admission.json', graph)
                if edit == 'focused': changed['focused_development_pass'] = True
                elif edit == 'old_tests': changed['expected_test_count'] = 473
                elif edit == 'cold_tests': changed['expected_test_count'] = 25
                elif edit == 'wrong_graph': changed['counts']['installed'] = 124
                else: write(root, 'graph-admission.json', dict(graph, source='copied_from_this_receipt'))
                write(root, 'community/passed.json', changed)
                with self.subTest(edit=edit), self.assertRaises(verifier.base.EvidenceError):
                    verifier.verify_receipt(root, {}, {}, 'community')


if __name__ == '__main__':
    unittest.main()
