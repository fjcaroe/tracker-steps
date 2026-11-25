"""Reject incomplete or fabricated evidence for the revised native OT flow."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_harvest_operations import exercise_revised_operations, MANIFEST_READ_PATH


class RevisedCopyClient:
    """A small API state machine; rejected transactions must leave no lines."""
    def __init__(self):
        self.scope = 'a' * 64
        self.rows = {}
        self.order = None
        self.posts = []
        self.approvers = [2]
        self.members = [11]
        self.centers = [{'id': 77, 'farm_id': 55, 'variety_id': 66, 'cuarteles': [{'id': 88}]}]
        self.fault = None
        self.serial = 0

    def bootstrap(self):
        return {'ok': True, 'scope': self.scope, 'user': {'id': 2, 'name': 'PRIVATE'},
                'company': {'id': 7, 'name': 'PRIVATE'}, 'approvers': [{'id': value} for value in self.approvers],
                'workers': [{'id': 11}], 'crews': [{'id': 33, 'worker_ids': self.members}],
                'farms': [{'id': 55}], 'varieties': [{'id': 66}], 'cost_centers': self.centers,
                'orders': [copy.deepcopy(self.order)] if self.order else []}

    def state(self, label, erp=None):
        if self.order['status'] != label:
            self.serial += 1
        self.order.update(status=label, state_changed_at=str(self.serial),
                          can_reopen=label in ('Cerrada', 'Revisada'))
        if erp:
            self.order['erp_state'] = erp

    def line(self, record):
        identifier = record['client_uuid']
        duplicate = identifier in self.rows
        if not duplicate:
            self.rows[identifier] = {'id': 123 + len(self.rows), 'mobile_uid': identifier,
                                     'registry_id': [22, 'PRIVATE']}
        return {'ok': True, 'duplicate': duplicate, 'id': self.rows[identifier]['id'],
                'client_uuid': identifier, 'work_order_id': 22}

    def request(self, method, path, payload=None):
        if path.endswith('/session'):
            return 200, dict(self.bootstrap(), connected=True)
        if path.endswith('/bootstrap'):
            return 200, self.bootstrap()
        if path == MANIFEST_READ_PATH:
            return 200, {'result': copy.deepcopy(list(self.rows.values()))}
        assert method == 'POST'
        self.posts.append(copy.deepcopy(payload))
        if payload['scope'] != self.scope:
            return 409, {'ok': False}
        if path.endswith('/sync'):
            record, = payload['records']
            if self.order and self.order['status'] != 'En proceso':
                return 200, {'ok': False}
            if not self.order:
                assert record['work_order']['approver_id'] == 2
                assert record['work_order']['cuartel_id'] == 88
                self.order = {'odoo_id': 22, 'crew_id': 33, 'approver_id': 2,
                              'status': 'En proceso', 'erp_state': 'in', 'can_reopen': False}
            result = self.line(record)
            if result['duplicate'] and self.fault == 'retry_identity':
                result['id'] += 1
            return 200, {'ok': True, 'results': [result]}
        assert path.endswith('/orders/transition')
        action = payload['action']
        manifest = payload['delivery_uuids']
        pending = payload.get('records', [])
        valid = set(manifest) == set(self.rows) | {row['client_uuid'] for row in pending}
        if not valid:
            if self.fault == 'leak_rejected_append':
                for row in pending:
                    self.line(row)
            return 422, {'ok': False}
        results = []
        if action == 'reopen':
            if self.order['status'] == 'Enviada' and self.fault != 'reopen_sent':
                return 422, {'ok': False}
            self.state('En proceso', 'in')
        elif action == 'close':
            self.state('Cerrada')
        elif action == 'approve':
            self.state('Revisada', 'in' if self.fault == 'no_native_approval' else 'apro')
            self.order.update(approved_by_id=2, approved_at='APPROVAL')
        elif action == 'send':
            results = [self.line(row) for row in pending]
            if self.fault == 'wrong_send_ack':
                results[0]['client_uuid'] = 'OTHER'
            self.state('Enviada', 'apro')
        else:
            raise AssertionError(action)
        return 200, {'ok': True, 'scope': self.scope, 'order': copy.deepcopy(self.order),
                     'confirmed_delivery_uuids': manifest, 'results': results}


class RevisedOperationsSmokeCase(unittest.TestCase):
    def exercise(self, client):
        return exercise_revised_operations(client, {'user_id': 2, 'company_id': 7},
                                           'QA-HARVEST-OPS-' + 'b' * 32)

    def test_complete_flow_creates_two_lines_and_proves_native_approval_and_total_queue(self):
        client = RevisedCopyClient()
        proof = self.exercise(client)
        self.assertEqual(len(client.rows), 2)
        self.assertEqual(proof['native_line_ids'], [123, 124])
        self.assertEqual(client.order['erp_state'], 'apro')
        self.assertEqual(client.order['status'], 'Enviada')
        self.assertTrue(proof['ot_reopen_before_send'] and proof['pending_send_atomic'])
        self.assertTrue(proof['sync_idempotency'] and proof['send_retry_idempotency'])
        self.assertTrue(proof['send_received_manifest'])
        self.assertNotIn('PRIVATE', json.dumps(proof))
        self.assertNotIn('review', [row.get('action') for row in client.posts])

    def test_missing_native_approver_member_or_coherent_masters_prevents_all_writes(self):
        for attribute, value in (('approvers', []), ('members', []), ('centers', []),
                                 ('centers', [{'id': 77, 'farm_id': 999, 'variety_id': 66}])):
            client = RevisedCopyClient()
            setattr(client, attribute, value)
            with self.subTest(attribute=attribute, value=value), self.assertRaises(AssertionError):
                self.exercise(client)
            self.assertEqual(client.posts, [])

    def test_wrong_native_state_identity_atomicity_or_reopening_cannot_be_certified(self):
        for fault in ('retry_identity', 'no_native_approval', 'leak_rejected_append',
                      'wrong_send_ack', 'reopen_sent'):
            client = RevisedCopyClient()
            client.fault = fault
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                self.exercise(client)


if __name__ == '__main__':
    unittest.main()
