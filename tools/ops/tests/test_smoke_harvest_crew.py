import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_harvest_crew import exercise_crew, validate_crew_policy


def policy_fixture(environment='development'):
    backend = 'a' * 40
    stage = 'management_' + environment + '_t236237_' + backend[:8]
    database = 'MANAGEMENT_QA_' + environment.upper() + '_t236237_' + backend[:8]
    frontend = {'repository': 'stepconsulting/step_harvest', 'version': '0.0.8', 'commit': 'b' * 40}
    proof = {'commit': backend, 'release_sha256': 'c' * 64, 'database': database,
             'environment': environment, 'feature': 'harvest-app', 'business_preserved': True}
    policy = {'environment': environment, 'harvest_web': frontend, 'database': database,
              'web_commit': frontend['commit'], 'read_only': False, 'copy_sync_allowed': True,
              'sync_origin': 'http://127.0.0.1:19001', 'user_id': 6, 'company_id': 17}
    return stage, proof, policy


class FakeCopy:
    def __init__(self, permissions=True):
        self.scope = 'd' * 64
        self.permissions = permissions
        self.posts = []
        self.worker = None
        self.attendance = None

    def request(self, method, path, payload=None):
        if method == 'GET':
            identity = {'ok': True, 'connected': True, 'scope': self.scope,
                        'user': {'id': 6}, 'company': {'id': 17}}
            if path.endswith('/session'):
                return 200, identity
            if path.endswith('/jobs'):
                return 200, {'ok': True, 'items': []}
            members = [21] + ([401] if self.worker else [])
            return 200, dict(identity, crew_permissions={'enroll': self.permissions, 'attendance': self.permissions},
                             crews=[{'id': 51, 'type': 'propio', 'worker_ids': members}],
                             workers=[dict(self.worker, id=401, job='Cosechero', job_id=8)] if self.worker else [],
                             crew_attendance=[{'crew_id': 51, 'date': self.attendance['date'], 'worker_ids': [401]}] if self.attendance else [])
        self.posts.append(copy.deepcopy(payload))
        if payload['scope'] != self.scope:
            return 409, {'ok': False}
        if payload['workers']:
            self.worker = self.worker or dict(payload['workers'][0])
            return 200, {'ok': True, 'worker_results': [{'client_uuid': self.worker['client_uuid'], 'ok': True, 'id': 401}], 'attendance_results': []}
        value = payload['attendances'][0]
        accepted = (value['date'] == value['entries'][0]['check_in'][:10]
                    and (self.attendance is None or self.attendance == value))
        if accepted:
            self.attendance = copy.deepcopy(value)
        result = {'client_uuid': value['client_uuid'], 'ok': accepted}
        result.update({'id': [501]} if accepted else {'error': 'Rejected changed attendance'})
        return 200, {'ok': accepted, 'worker_results': [], 'attendance_results': [result]}


class CrewSmokeSafetyCase(unittest.TestCase):
    def test_only_exact_certified_operations_copy_is_accepted(self):
        for environment in ('development', 'cerro', 'qa-cerro'):
            stage, proof, policy = policy_fixture(environment)
            validate_crew_policy(policy['sync_origin'], stage, proof, policy)
        for change in ({'user_id': 1}, {'copy_sync_allowed': False}, {'read_only': True}, {'database': 'CERRO_EL_PLOMO'}, {'sync_origin': 'http://127.0.0.1:19002'}):
            stage, proof, policy = policy_fixture()
            with self.assertRaises(AssertionError):
                validate_crew_policy('http://127.0.0.1:19001', stage, proof, dict(policy, **change))
        for change in ({'feature': 'harvest-android-pilot'}, {'business_preserved': False}, {'commit': 'a'*8}, {'readonly_copy': True}):
            stage, proof, policy = policy_fixture()
            with self.assertRaises(AssertionError):
                validate_crew_policy(policy['sync_origin'], stage, dict(proof, **change), policy)
        stage, proof, policy = policy_fixture()
        for origin in ('https://desarrollo.stepsapp.cl', 'http://localhost:19001', 'http://127.0.0.1:19001/api', 'http://127.0.0.1:19001?destination=live'):
            with self.assertRaises(AssertionError):
                validate_crew_policy(origin, stage, proof, policy)

    def test_enrollment_and_attendance_complete_with_same_native_ids_on_retry(self):
        _, _, policy = policy_fixture()
        client = FakeCopy()
        result = exercise_crew(client, policy, 'UTC', 'QA-HARVEST-CREW-' + 'e' * 32)
        self.assertTrue(result['worker_enrollment'])
        self.assertTrue(result['attendance_idempotency'])
        self.assertTrue(result['changed_attendance_rejected'])
        self.assertNotIn('nip', result)
        self.assertNotIn('name', result)
        self.assertNotEqual(client.posts[0]['scope'], client.scope)

    def test_missing_existing_permissions_fails_before_any_write(self):
        _, _, policy = policy_fixture()
        client = FakeCopy(permissions=False)
        with self.assertRaises(AssertionError):
            exercise_crew(client, policy, 'UTC')
        self.assertEqual(client.posts, [])


if __name__ == '__main__':
    unittest.main()
