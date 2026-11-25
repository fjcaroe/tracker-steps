import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configure_harvest_default_job import (BACKEND_COMMIT, bind_configuration_smoke, read_release,
    stage_identity, validate_all_copies, validate_backup, validate_certificate, validate_configuration_proof, validate_crew_smoke)


PACKAGE_SHA, HELPER_SHA = 'a'*64, 'b'*64


def fixtures(environment='development'):
    stage, database = stage_identity(environment)
    proof = {'environment': environment, 'database': database, 'commit': BACKEND_COMMIT,
             'release_sha256': PACKAGE_SHA, 'feature': 'harvest-app', 'business_preserved': True}
    release = {'commit': BACKEND_COMMIT, 'versions': {'step_harvest_launcher': '18.0.1.4.0'}}
    configuration = {'environment': environment, 'stage': stage, 'database': database, 'mode': 'copy',
        'applied': True, 'commit': BACKEND_COMMIT, 'release_sha256': PACKAGE_SHA,
        'helper_sha256': HELPER_SHA, 'company_id': 1, 'user_id': 6, 'job_id': 31,
        'previous_jobs_preserved': True, 'employees_preserved': True, 'roles_preserved': True,
        'permissions_preserved': True, 'created_at': '2026-11-25T01:00:00+00:00'}
    smoke = {'stage': stage, 'database': database, 'feature': 'harvest-app', 'backend_commit': BACKEND_COMMIT,
        'backend_sha256': PACKAGE_SHA, 'default_job_helper_sha256': HELPER_SHA, 'native_job_id': 31,
        'company_id': 1, 'user_id': 6, 'credentials_or_session_ids_supplied': False,
        'native_worker_id': 41, 'native_attendance_id': 51, 'native_crew_id': 61,
        'new_workers': 1, 'new_attendances': 1,
        'created_at': '2026-11-25T01:01:00+00:00'}
    for key in ('worker_enrollment', 'crew_attendance', 'attendance_home_total', 'native_job_default',
                'scope_rejected_before_write', 'enrollment_idempotency', 'attendance_idempotency',
                'changed_hours_rejected', 'wrong_date_rejected', 'native_context', 'native_members_preserved'):
        smoke[key] = True
    return stage, proof, release, configuration, smoke


class DefaultJobGuardsCase(unittest.TestCase):
    def test_only_exact_frozen_package_and_certified_destination_are_accepted(self):
        for environment in ('development', 'cerro', 'qa-cerro'):
            stage, proof, release, _, _ = fixtures(environment)
            validate_certificate(environment, stage, proof, PACKAGE_SHA, release)
        stage, proof, release, _, _ = fixtures()
        for key, value in (('commit', 'c'*40), ('database', 'LAB_TAREAS'), ('environment', 'cerro'),
                           ('feature', 'harvest-android-pilot'), ('business_preserved', False),
                           ('release_sha256', 'c'*64), ('readonly_copy', True)):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate_certificate('development', stage, dict(proof, **{key:value}), PACKAGE_SHA, release)
        with self.assertRaises(AssertionError):
            validate_certificate('development', stage+'_different', proof, PACKAGE_SHA, release)

    def test_copy_proof_requires_committed_configuration_same_helper_and_preservation(self):
        _, _, _, configuration, _ = fixtures()
        validate_configuration_proof(configuration, 'development', PACKAGE_SHA, HELPER_SHA)
        for key, value in (('applied', False), ('mode', 'live'), ('helper_sha256', 'c'*64),
                           ('company_id', 2), ('user_id', 1), ('job_id', 0), ('roles_preserved', False),
                           ('employees_preserved', False), ('permissions_preserved', False)):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate_configuration_proof(dict(configuration, **{key:value}), 'development', PACKAGE_SHA, HELPER_SHA)

    def test_smoke_must_follow_configuration_and_match_native_job_and_context(self):
        _, _, _, configuration, smoke = fixtures()
        validate_crew_smoke(smoke, configuration, 'development', PACKAGE_SHA, HELPER_SHA)
        for key, value in (('native_job_id', 32), ('default_job_helper_sha256', 'c'*64),
                           ('created_at', '2026-11-25T00:59:00+00:00'), ('company_id', 2), ('user_id', 1),
                           ('attendance_idempotency', False), ('credentials_or_session_ids_supplied', True)):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate_crew_smoke(dict(smoke, **{key:value}), configuration, 'development', PACKAGE_SHA, HELPER_SHA)

    def test_smoke_binding_uses_current_helper_and_actual_native_job(self):
        _, _, _, configuration, smoke = fixtures()
        unbound = dict(smoke); unbound.pop('default_job_helper_sha256')
        bound = bind_configuration_smoke(unbound, configuration, 'development', PACKAGE_SHA, HELPER_SHA)
        self.assertNotIn('default_job_helper_sha256', unbound)
        self.assertEqual(bound['default_job_helper_sha256'], HELPER_SHA)
        with self.assertRaises(AssertionError):
            bind_configuration_smoke(dict(unbound, native_job_id=99), configuration, 'development', PACKAGE_SHA, HELPER_SHA)

    def test_live_gate_requires_three_matching_copy_configurations_and_smokes(self):
        with tempfile.TemporaryDirectory() as directory:
            stages = Path(directory).resolve()
            for environment in ('development', 'cerro', 'qa-cerro'):
                name, proof, release, configuration, smoke = fixtures(environment)
                stage = stages/name; stage.mkdir()
                (stage/'qa_passed.json').write_text(json.dumps(proof))
                (stage/'harvest-default-job-copy.json').write_text(json.dumps(configuration))
                (stage/'harvest-crew-smoke.json').write_text(json.dumps(smoke))
            validate_all_copies(stages, PACKAGE_SHA, HELPER_SHA, release)
            last = stages/stage_identity('qa-cerro')[0]/'harvest-crew-smoke.json'
            original = last.read_text(); bad = json.loads(original); bad['default_job_helper_sha256'] = 'c'*64
            last.write_text(json.dumps(bad))
            with self.assertRaises(AssertionError): validate_all_copies(stages, PACKAGE_SHA, HELPER_SHA, release)
            last.unlink()
            with self.assertRaises(FileNotFoundError): validate_all_copies(stages, PACKAGE_SHA, HELPER_SHA, release)

    def test_backup_requires_nonempty_dump_matching_deployment_and_first_overlay(self):
        environment = 'cerro'
        overlay = Path('/opt/steps-managed/releases')/environment/BACKEND_COMMIT
        backup = Path('/opt/steps_backups/management_cerro_20261125T010000Z')
        deployment = {'commit': BACKEND_COMMIT, 'sha256': PACKAGE_SHA, 'overlay': str(overlay), 'log': '/opt/steps-validation/deploy.log'}
        with patch.object(Path, 'resolve', lambda path: path), patch.object(Path, 'is_symlink', return_value=False), \
             patch.object(Path, 'is_file', return_value=True), patch.object(Path, 'stat', return_value=SimpleNamespace(st_size=1)):
            validate_backup(environment, backup, deployment, PACKAGE_SHA, overlay)
            for key, value in (('commit', 'c'*40), ('sha256', 'c'*64), ('overlay', str(overlay.parent/'other'))):
                with self.subTest(key=key), self.assertRaises(AssertionError):
                    validate_backup(environment, backup, dict(deployment, **{key:value}), PACKAGE_SHA, overlay)
            with self.assertRaises(AssertionError):
                validate_backup(environment, backup, deployment, PACKAGE_SHA, overlay.parent)
            with patch.object(Path, 'stat', return_value=SimpleNamespace(st_size=0)), self.assertRaises(AssertionError):
                validate_backup(environment, backup, deployment, PACKAGE_SHA, overlay)

    def test_release_hashes_are_verified_without_extracting_or_trusting_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)/'release.tar.gz'
            data = b'private test addon bytes'
            release = {'commit': BACKEND_COMMIT, 'versions': {'step_harvest_launcher':'18.0.1.4.0'},
                       'files': {'step_harvest_launcher/models.py':hashlib.sha256(data).hexdigest()}}
            def write(name, contents):
                with tarfile.open(package, 'w:gz') as archive:
                    for filename, content in (('release.json',json.dumps(release).encode()),(name,contents)):
                        member = tarfile.TarInfo(filename); member.size = len(content)
                        archive.addfile(member,io.BytesIO(content))
            write('step_harvest_launcher/models.py',data)
            self.assertEqual(read_release(package),release)
            write('step_harvest_launcher/models.py',b'changed')
            with self.assertRaises(AssertionError): read_release(package)
            write('../outside.py',data)
            with self.assertRaises(AssertionError): read_release(package)
            self.assertFalse((Path(directory)/'outside.py').exists())


if __name__ == '__main__':
    unittest.main()
