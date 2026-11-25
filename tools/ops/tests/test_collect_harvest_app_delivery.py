from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collect_harvest_app_delivery import validate_default_job_delivery
from configure_harvest_default_job import BACKEND_COMMIT, stage_identity


PACKAGE_SHA, HELPER_SHA = 'a' * 64, 'b' * 64
LIVE_DATABASES = {'development': 'LAB_TAREAS', 'qa-cerro': 'QA-CERROELPLOMO', 'cerro': 'CERRO_EL_PLOMO'}
BACKUPS = {environment: '/opt/steps_backups/management_' + environment + '_20261125T000000Z' for environment in LIVE_DATABASES}
PRESERVATION = ('previous_jobs_preserved', 'employees_preserved', 'roles_preserved', 'permissions_preserved')


def fixtures(environment='development'):
    stage, database = stage_identity(environment)
    configured = {'environment': environment, 'stage': stage, 'database': database, 'mode': 'copy',
                  'applied': True, 'commit': BACKEND_COMMIT, 'release_sha256': PACKAGE_SHA,
                  'helper_sha256': HELPER_SHA, 'company_id': 1, 'user_id': 6, 'job_id': 10}
    configured.update(dict.fromkeys(PRESERVATION, True))
    live = dict(configured, mode='live', database=LIVE_DATABASES[environment], job_id=20, backup=BACKUPS[environment])
    qa = {'database': database, 'commit': BACKEND_COMMIT, 'release_sha256': PACKAGE_SHA}
    return configured, live, qa


def validate(values, environment='development'):
    validate_default_job_delivery(*values, environment, PACKAGE_SHA, HELPER_SHA, LIVE_DATABASES[environment], BACKUPS[environment])


class HarvestConfigurationCollectionCase(unittest.TestCase):
    def test_other_deployment_backup_is_rejected(self):
        values = fixtures()
        values[1]['backup'] = BACKUPS['cerro']
        with self.assertRaises(AssertionError):
            validate(values)

    def test_copy_and_live_can_have_distinct_native_job_ids(self):
        for environment in LIVE_DATABASES:
            with self.subTest(environment=environment):
                validate(fixtures(environment), environment)

    def test_wrong_package_helper_profile_or_destination_is_rejected(self):
        cases = [('mode', 'live'), ('applied', False), ('environment', 'cerro'),
                 ('stage', 'management_development_t236237_other'), ('commit', 'c' * 40),
                 ('release_sha256', 'd' * 64), ('helper_sha256', 'e' * 64),
                 ('company_id', 2), ('user_id', 1)]
        for index in (0, 1):
            for key, value in cases:
                # Each side has its own required mode.
                if index == 1 and key == 'mode':
                    value = 'copy'
                with self.subTest(side=index, key=key):
                    values = fixtures()
                    values[index][key] = value
                    with self.assertRaises(AssertionError):
                        validate(values)
        for index, database in ((0, LIVE_DATABASES['development']), (1, stage_identity('development')[1])):
            values = fixtures()
            values[index]['database'] = database
            with self.subTest(side=index, key='database'), self.assertRaises(AssertionError):
                validate(values)

    def test_missing_preservation_or_invalid_job_is_rejected_on_either_side(self):
        for index in (0, 1):
            for key in PRESERVATION:
                for missing in (False, True):
                    values = fixtures()
                    if missing:
                        del values[index][key]
                    else:
                        values[index][key] = False
                    with self.subTest(side=index, key=key, missing=missing), self.assertRaises(AssertionError):
                        validate(values)
            for job in (0, -1, True, '10'):
                values = fixtures()
                values[index]['job_id'] = job
                with self.subTest(side=index, job=job), self.assertRaises(AssertionError):
                    validate(values)

    def test_configuration_must_belong_to_the_collected_copy_certificate(self):
        for key, value in (('database', 'ANOTHER_COPY'), ('commit', 'f' * 40), ('release_sha256', 'f' * 64)):
            values = fixtures()
            values[2][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validate(values)


if __name__ == '__main__':
    unittest.main()
