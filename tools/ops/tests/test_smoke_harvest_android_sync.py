"""The native copy smoke rejects unsafe targets and proves scope/retry semantics."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_harvest_android_sync import exercise_sync, review_origin, validate_review_policy


class NativeClient:
    def __init__(self):
        self.posts = []
        self.first_duplicate = False
        self.retry_id = 123
        self.reject_scope = True
        self.bootstrap = {'ok': True, 'scope': 'a'*64,
            'user': {'id': 2, 'name': 'PRIVATE USER NAME'},
            'company': {'id': 7, 'name': 'PRIVATE COMPANY NAME'},
            'workers': [{'id': 11, 'name': 'PRIVATE WORKER NAME'}],
            'orders': [{'odoo_id': 22, 'status': 'En proceso', 'name': 'PRIVATE OT NAME'}]}

    def request(self, method, path, payload=None):
        if path == '/api/harvest/session':
            return 200, dict(self.bootstrap, connected=True)
        if path == '/api/harvest/health':
            return 200, {'ok': True, 'scope': self.bootstrap['scope'], 'capabilities': ['context_scope']}
        if path == '/api/harvest/bootstrap':
            return 200, self.bootstrap
        assert method == 'POST' and path == '/api/harvest/sync'
        self.posts.append(copy.deepcopy(payload))
        record = payload['records'][0]
        if payload['scope'] != self.bootstrap['scope'] and self.reject_scope:
            return 409, {'ok': False}
        duplicate = len(self.posts) > 2 or self.first_duplicate
        return 200, {'ok': True, 'results': [{'ok': True, 'duplicate': duplicate,
            'id': self.retry_id if duplicate else 123, 'client_uuid': record['client_uuid'],
            'work_order_id': record['work_order']['odoo_id']}]}


class CopySmokeCase(unittest.TestCase):
    def setUp(self):
        self.policy = {'user_id': 2, 'company_id': 7}
        self.run_uuid = 'QA-HARVEST-ANDROID-' + '1'*32

    def test_exact_loopback_only_no_remote_or_credential_targets(self):
        self.assertEqual(review_origin('http://127.0.0.1:8777/'), 'http://127.0.0.1:8777')
        for value in ('https://desarrollo.stepsapp.cl', 'http://localhost:8777',
                      'http://127.0.0.1:8777/cosecha/', 'http://127.0.0.1:8777?x=1',
                      'http://user@127.0.0.1:8777', 'http://127.0.0.1:80',
                      'http://127.0.0.1:8777#fragment'):
            with self.subTest(url=value), self.assertRaises(AssertionError):
                review_origin(value)

    def test_smoke_checks_native_result_and_omits_private_names(self):
        client = NativeClient()
        evidence = exercise_sync(client, self.policy, self.run_uuid)
        self.assertTrue(evidence['native_copy_sync'] and evidence['sync_idempotency'])
        self.assertEqual(len(client.posts), 3)
        self.assertNotEqual(client.posts[0]['scope'], client.posts[1]['scope'])
        self.assertEqual(client.posts[1], client.posts[2])
        record = client.posts[1]['records'][0]
        self.assertEqual(record['worker_id'], 11)
        self.assertEqual(record['work_order'], {'odoo_id': 22})
        self.assertNotIn('PRIVATE', json.dumps(evidence))
        self.assertNotIn('worker_id', evidence)
        self.assertNotIn('user_id', evidence)

    def test_empty_catalog_and_changed_identity_stop_before_any_write(self):
        for changed in ('workers', 'orders', 'user', 'company'):
            client = NativeClient()
            client.bootstrap[changed] = [] if changed in ('workers', 'orders') else {'id': 999}
            with self.subTest(changed=changed), self.assertRaises(AssertionError):
                exercise_sync(client, self.policy, self.run_uuid)
            self.assertEqual(client.posts, [])

    def test_scope_bypass_preexisting_uuid_or_retry_change_cannot_pass(self):
        for field, value in (('reject_scope', False), ('first_duplicate', True), ('retry_id', 124)):
            client = NativeClient()
            setattr(client, field, value)
            with self.subTest(field=field), self.assertRaises(AssertionError):
                exercise_sync(client, self.policy, self.run_uuid)

    def test_review_certificate_cannot_be_reused_on_live_or_readonly_proxy(self):
        stage = 'management_development_harvestandroid_' + 'b'*8
        frontend = {'version': '0.0.7', 'commit': 'b'*40, 'files': {}}
        proof = {'harvest_web': frontend, 'feature': 'harvest-android-pilot',
            'readonly_copy': True, 'business_preserved': True,
            'commit': 'c'*40, 'release_sha256': 'd'*64,
            'database': 'MANAGEMENT_QA_DEVELOPMENT_harvestandroid_' + 'b'*8}
        policy = dict(self.policy, environment='development', database=proof['database'],
            web_commit=frontend['commit'], read_only=False, copy_sync_allowed=True,
            sync_origin='http://127.0.0.1:8777')
        validate_review_policy('http://127.0.0.1:8777', stage, proof, policy)
        for key, value in (('database', 'LAB_TAREAS'), ('read_only', True),
                           ('copy_sync_allowed', False), ('web_commit', 'e'*40),
                           ('sync_origin', 'http://127.0.0.1:8778')):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate_review_policy('http://127.0.0.1:8777', stage, proof, dict(policy, **{key: value}))


if __name__ == '__main__':
    unittest.main()
