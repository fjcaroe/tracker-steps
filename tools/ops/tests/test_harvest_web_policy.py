"""The Android static pilot cannot escape its certified copy or existing profile."""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harvest_web_policy import (ANDROID_REVIEW_CHECKS, is_copy_sync_request,
    require_copy_sync_certificate, static_copy_identity, validate_android_review,
    validate_static_copy, validate_operations_copy, validate_operations_review,
    OPERATIONS_REVIEW_CHECKS)
from native_business_profile import scoped_existing_user_environment


class AndroidPolicyCase(unittest.TestCase):
    def setUp(self):
        self.frontend = {'repository': 'stepconsulting/step_harvest',
            'version': '0.0.7', 'commit': 'a'*40,
            'files': {'app/index.html': '1'*64}}
        self.stage = 'management_development_harvestandroid_' + 'a'*8
        self.proof = {'feature': 'harvest-android-pilot', 'readonly_copy': True,
            'business_preserved': True, 'harvest_web': copy.deepcopy(self.frontend),
            'commit': 'b'*40, 'release_sha256': 'c'*64,
            'database': 'MANAGEMENT_QA_DEVELOPMENT_harvestandroid_' + 'a'*8}
        self.review = {'reviewed': True, 'web_commit': 'a'*40,
            'backend_commit': 'b'*40, 'backend_sha256': 'c'*64,
            'database': self.proof['database'],
            **dict.fromkeys(ANDROID_REVIEW_CHECKS, True)}

    def test_existing_company_copy_remains_supported(self):
        frontend = dict(self.frontend, version='0.0.4')
        for environment in ('development', 'cerro', 'qa-cerro'):
            run_id, feature = static_copy_identity(frontend, environment)
            self.assertEqual(run_id, 'harvestcompany_' + 'a'*8)
            self.assertEqual(feature, 'harvest-company-selector')

    def test_android_identity_is_development_only(self):
        self.assertEqual(static_copy_identity(self.frontend, 'development'),
            ('harvestandroid_' + 'a'*8, 'harvest-android-pilot'))
        for environment in ('cerro', 'qa-cerro', 'sys', 'steps', 'demo'):
            with self.subTest(environment=environment), self.assertRaises(AssertionError):
                static_copy_identity(self.frontend, environment)
        with self.assertRaises(AssertionError):
            static_copy_identity(dict(self.frontend, version='0.0.6'), 'development')

    def test_copy_binds_version_files_identity_preservation_and_feature(self):
        validate_static_copy(self.frontend, 'development', self.stage, self.proof)
        for key, value in (
                ('feature', 'harvest-company-selector'), ('readonly_copy', False),
                ('readonly_copy', 1), ('business_preserved', False),
                ('database', 'LAB_TAREAS'), ('commit', 'invalid'),
                ('release_sha256', '0'*40),
                ('harvest_web', dict(self.frontend, files={'app/index.html': '2'*64}))):
            with self.subTest(key=key, value=value), self.assertRaises(AssertionError):
                validate_static_copy(self.frontend, 'development', self.stage,
                    dict(self.proof, **{key: value}))
        with self.assertRaises(AssertionError):
            validate_static_copy(self.frontend, 'development',
                'management_development_harvestcompany_' + 'a'*8, self.proof)

    def test_publish_requires_each_mobile_check_and_exact_backend(self):
        validate_android_review(self.frontend, 'development', self.stage, self.proof, self.review)
        for key in ANDROID_REVIEW_CHECKS:
            for value in (False, 1):
                with self.subTest(key=key, value=value), self.assertRaises(AssertionError):
                    validate_android_review(self.frontend, 'development', self.stage,
                        self.proof, dict(self.review, **{key: value}))
        for key in ('web_commit', 'backend_commit', 'backend_sha256', 'database'):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate_android_review(self.frontend, 'development', self.stage,
                    self.proof, dict(self.review, **{key: 'different'}))

    def test_sync_requires_android_copy_certificate(self):
        require_copy_sync_certificate(self.frontend, 'development', self.stage, self.proof)
        for changed in (dict(self.proof, readonly_copy=False),
                        dict(self.proof, business_preserved=False),
                        dict(self.proof, feature='harvest-company-selector')):
            with self.assertRaises(AssertionError):
                require_copy_sync_certificate(self.frontend, 'development', self.stage, changed)
        with self.assertRaises(AssertionError):
            require_copy_sync_certificate(dict(self.frontend, version='0.0.4'),
                'development', self.stage, self.proof)

    def test_sync_only_accepts_explicit_exact_loopback_post(self):
        origin = 'http://127.0.0.1:8177'
        self.assertTrue(is_copy_sync_request(True, 'POST', '/api/harvest/sync', origin, 8177))
        rejected = [
            (False, 'POST', '/api/harvest/sync', origin),
            (True, 'GET', '/api/harvest/sync', origin),
            (True, 'POST', '/api/harvest/sync?extra=1', origin),
            (True, 'POST', '/web/dataset/call_kw', origin),
            (True, 'POST', '/api/harvest/sync', None),
            (True, 'POST', '/api/harvest/sync', 'http://localhost:8177'),
            (True, 'POST', '/api/harvest/sync', 'http://127.0.0.1:8178'),
            (True, 'POST', '/api/harvest/sync', 'https://desarrollo.stepsapp.cl'),
            (True, 'POST', '/api/harvest/sync', origin + '.example'),
        ]
        for enabled, method, path, supplied in rejected:
            with self.subTest(path=path, origin=supplied):
                self.assertFalse(is_copy_sync_request(enabled, method, path, supplied, 8177))


class OperationsPolicyCase(unittest.TestCase):
    def setUp(self):
        self.frontend = {'repository': 'stepconsulting/step_harvest',
            'version': '0.0.8', 'commit': 'a'*40, 'files': {'app/index.html': '1'*64}}
        self.proof = {'commit': 'b'*40, 'release_sha256': 'c'*64,
            'database': 'MANAGEMENT_QA_QA-CERRO_t236237_' + 'b'*8,
            'feature': 'harvest-app', 'environment': 'qa-cerro', 'business_preserved': True}
        self.stage = 'management_qa-cerro_t236237_' + 'b'*8
        self.review = {'reviewed': True, 'web_commit': 'a'*40,
            'backend_commit': 'b'*40, 'backend_sha256': 'c'*64,
            'database': self.proof['database'], **dict.fromkeys(OPERATIONS_REVIEW_CHECKS, True)}

    def test_operations_requires_its_native_copy_and_preservation(self):
        validate_operations_copy(self.frontend, 'qa-cerro', self.stage, self.proof)
        require_copy_sync_certificate(self.frontend, 'qa-cerro', self.stage, self.proof)
        for key, value in (('database', 'QA-CERROELPLOMO'), ('commit', 'a'*40),
                ('feature', 'harvest-android-pilot'), ('environment', 'cerro'),
                ('business_preserved', False), ('readonly_copy', True)):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate_operations_copy(self.frontend, 'qa-cerro', self.stage,
                    dict(self.proof, **{key: value}))
        with self.assertRaises(AssertionError):
            validate_operations_copy(self.frontend, 'cerro', self.stage, self.proof)

    def test_publish_requires_confirmed_transitions_attendance_and_exact_backend(self):
        validate_operations_review(self.frontend, 'qa-cerro', self.stage, self.proof, self.review)
        for key in (*OPERATIONS_REVIEW_CHECKS, 'web_commit', 'backend_commit', 'backend_sha256', 'database'):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate_operations_review(self.frontend, 'qa-cerro', self.stage,
                    self.proof, dict(self.review, **{key: False}))

    def test_new_copy_writes_keep_android_and_published_origins_restricted(self):
        origin = 'http://127.0.0.1:8177'
        for path in ('/api/harvest/crew/sync', '/api/harvest/work-orders/lifecycle'):
            self.assertTrue(is_copy_sync_request(True, 'POST', path, origin, 8177, '0.0.8'))
            self.assertFalse(is_copy_sync_request(True, 'POST', path, origin, 8177))
            self.assertFalse(is_copy_sync_request(False, 'POST', path, origin, 8177, '0.0.8'))
            self.assertFalse(is_copy_sync_request(True, 'POST', path, 'https://qa-cerroelplomo.stepsapp.cl', 8177, '0.0.8'))
            self.assertFalse(is_copy_sync_request(True, 'POST', path+'?x=1', origin, 8177, '0.0.8'))
        self.assertFalse(is_copy_sync_request(True, 'POST', '/web/dataset/call_kw', origin, 8177, '0.0.8'))


class Company:
    def __init__(self, identifier):
        self.id = identifier
        self.ids = [identifier] if identifier else []

    def __len__(self):
        return len(self.ids)


class ExistingUser:
    def __init__(self, company, active=True, share=False, exists=True):
        self.active, self.share, self.present = active, share, exists
        self.company_id = company
        self.company_ids = [company]

    def __len__(self):
        return int(self.present)

    def exists(self):
        return self


class ExistingEnvironment:
    def __init__(self, user):
        self.user_record = user
        self.context = {'lang': 'es_CL'}
        self.calls = []

    def __getitem__(self, model):
        assert model == 'res.users'
        return SimpleNamespace(browse=lambda identifier: self.user_record)

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(user=kwargs['user'], su=kwargs['su'],
            company=self.user_record.company_id)


class ExistingProfileCase(unittest.TestCase):
    def test_existing_profile_uses_its_company_and_disables_superuser(self):
        company = Company(10)
        user = ExistingUser(company)
        env = ExistingEnvironment(user)
        result = scoped_existing_user_environment(env, 2)
        self.assertIs(result.user, user)
        self.assertFalse(result.su)
        self.assertEqual(env.calls, [{'user': user, 'su': False,
            'context': {'lang': 'es_CL', 'allowed_company_ids': [10]}}])

    def test_unknown_inactive_portal_foreign_or_superuser_never_falls_back(self):
        company = Company(10)
        for options in ({'active': False}, {'share': True}, {'exists': False}):
            env = ExistingEnvironment(ExistingUser(company, **options))
            with self.subTest(options=options), self.assertRaises(AssertionError):
                scoped_existing_user_environment(env, 2)
            self.assertEqual(env.calls, [])
        env = ExistingEnvironment(ExistingUser(company))
        for identifier, chosen in ((1, company), (0, company), (2, Company(11)), (2, Company(None))):
            with self.subTest(user_id=identifier), self.assertRaises(AssertionError):
                scoped_existing_user_environment(env, identifier, company=chosen)
            self.assertEqual(env.calls, [])


if __name__ == '__main__':
    unittest.main()
