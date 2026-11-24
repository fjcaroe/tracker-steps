"""The operations smoke cannot accept a live target or a fabricated success."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_harvest_operations import exercise_operations, validate_operations_policy, OperationsClient
from smoke_harvest_android_sync import ReviewClient, review_origin


class CopyClient:
    def __init__(self):
        self.scope = 'a'*64
        self.status = 'En proceso'
        self.posts = []
        self.line_id = 123
        self.has_delivery = False
        self.bypass_scope = False
        self.bypass_manifest = False
        self.accept_after_close = False
        self.repeat_id = 123
        self.order = {'odoo_id': 22, 'status': self.status, 'erp_state': 'in', 'can_transition': True}

    def bootstrap(self):
        return {'ok': True, 'scope': self.scope, 'user': {'id': 2, 'name': 'PRIVATE USER'},
                'company': {'id': 7, 'name': 'PRIVATE COMPANY'},
                'workers': [{'id': 11, 'name': 'PRIVATE WORKER'}],
                'orders': [dict(self.order, status=self.status)]}

    def request(self, method, path, payload=None):
        if path.endswith('/session'):
            return 200, dict(self.bootstrap(), connected=True)
        if path.endswith('/bootstrap'):
            return 200, self.bootstrap()
        assert method == 'POST'
        self.posts.append(copy.deepcopy(payload))
        if payload['scope'] != self.scope and not self.bypass_scope:
            return 409, {'ok': False}
        if path.endswith('/sync'):
            record = payload['records'][0]
            if record['client_uuid'].endswith('-AFTER-CLOSE') and not self.accept_after_close:
                return 200, {'ok': False, 'results': [{'ok': False}]}
            result = {'ok': True, 'duplicate': self.has_delivery,
                'id': self.repeat_id if self.has_delivery else self.line_id,
                'client_uuid': record['client_uuid'], 'work_order_id': 22}
            self.has_delivery = True
            return 200, {'ok': True, 'results': [result]}
        assert path.endswith('/orders/transition')
        if len(payload['delivery_uuids']) != 1 and not self.bypass_manifest:
            return 422, {'ok': False}
        self.status = {'close': 'Cerrada', 'review': 'Revisada', 'send': 'Enviada'}[payload['action']]
        return 200, {'ok': True, 'scope': self.scope, 'confirmed_delivery_uuids': payload['delivery_uuids'],
                     'order': dict(self.order, status=self.status, state_changed_at='PRIVATE TIMESTAMP')}


class OperationsSmokeCase(unittest.TestCase):
    def test_complete_native_flow_uses_one_original_uuid_and_omits_names(self):
        client = CopyClient()
        result = exercise_operations(client, {'user_id': 2, 'company_id': 7}, 'QA-HARVEST-OPS-' + 'b'*32)
        self.assertEqual(result['new_lines'], 1)
        self.assertTrue(result['ot_send_confirmation'])
        self.assertTrue(result['erp_state_preserved'])
        self.assertEqual(client.status, 'Enviada')
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_missing_or_already_approved_order_prevents_any_post(self):
        for change in ({'erp_state': 'apro'}, {'status': 'Cerrada'}, {'can_transition': False}):
            client = CopyClient()
            if 'status' in change:
                client.status = change['status']
            client.order.update(change)
            with self.assertRaises(AssertionError):
                exercise_operations(client, {'user_id': 2, 'company_id': 7})
            self.assertEqual(client.posts, [])

    def test_bypassed_scope_manifest_duplicate_identity_or_close_block_fails(self):
        for attr, value in [('bypass_scope', True), ('bypass_manifest', True),
                            ('repeat_id', 124), ('accept_after_close', True), ('has_delivery', True)]:
            client = CopyClient()
            setattr(client, attr, value)
            with self.subTest(attr=attr), self.assertRaises(AssertionError):
                exercise_operations(client, {'user_id': 2, 'company_id': 7})

    def test_clients_reject_live_urls_and_keep_android_write_paths_restricted(self):
        for url in ('https://desarrollo.stepsapp.cl', 'http://localhost:8777', 'http://127.0.0.1:8777/path',
                    'http://127.0.0.1:8777?target=live', 'http://user:password@127.0.0.1:8777'):
            with self.subTest(url=url), self.assertRaises(AssertionError):
                OperationsClient(url)
        self.assertEqual(review_origin('http://127.0.0.1:8777'), 'http://127.0.0.1:8777')
        self.assertNotIn(('POST', '/api/harvest/orders/transition'), ReviewClient.allowed_requests)
        self.assertIn(('POST', '/api/harvest/orders/transition'), OperationsClient.allowed_requests)

    def test_certificate_requires_exact_stage_backend_copy_and_proxy(self):
        frontend = {'version': '0.0.8', 'commit': 'c'*40, 'files': {}}
        proof = {'commit': 'b'*40, 'release_sha256': 'd'*64, 'feature': 'harvest-app',
                 'database': 'MANAGEMENT_QA_CERRO_t236237_' + 'b'*8,
                 'business_preserved': True}
        policy = {'environment': 'cerro', 'database': proof['database'], 'web_commit': frontend['commit'],
                  'read_only': False, 'copy_sync_allowed': True, 'sync_origin': 'http://127.0.0.1:8777',
                  'user_id': 2, 'company_id': 7, 'harvest_web': frontend}
        stage = 'management_cerro_t236237_' + 'b'*8
        # The shared policy is validated by its own suite. Check this helper
        # invokes it and adds strict package/stage/profile requirements.
        with patch('smoke_harvest_operations.require_copy_sync_certificate') as guard:
            validate_operations_policy(policy['sync_origin'], stage, proof, policy)
            guard.assert_called_once_with(frontend, 'cerro', stage, proof)
            for key, value in [('database', 'CERRO_EL_PLOMO'), ('read_only', True),
                               ('sync_origin', 'http://127.0.0.1:8778'), ('user_id', 1),
                               ('copy_sync_allowed', False), ('environment', 'development'),
                               ('web_commit', 'e'*40), ('harvest_web', dict(frontend, version='0.0.7'))]:
                with self.subTest(key=key), self.assertRaises(AssertionError):
                    validate_operations_policy(policy['sync_origin'], stage, proof, dict(policy, **{key: value}))
            for key, value in [('business_preserved', False), ('commit', 'e'*40),
                               ('release_sha256', 'broken'), ('feature', 'harvestandroid')]:
                with self.subTest(key=key), self.assertRaises(AssertionError):
                    validate_operations_policy(policy['sync_origin'], stage, dict(proof, **{key: value}), policy)


if __name__ == '__main__':
    unittest.main()
