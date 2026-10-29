"""Pure admission-upgrade witnesses: no ORM, database or payment is simulated."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import validate_payroll_admission_upgrade as probe
import validate_payroll_properties_upgrade as legacy
from validate_payroll_properties_upgrade_test import fixtures as property_fixtures


def fixtures():
    before, after, audit = property_fixtures()
    # F already stores rule properties as JSON. The new runner must not apply
    # the old 1.9 scalar -> JSON projection a second time.
    before['hr_salary_rule'] = copy.deepcopy(after['hr_salary_rule'])
    before['property_columns'] = copy.deepcopy(after['property_columns'])
    for table in ('hr_payroll_structure', 'hr_payroll_structure_type'):
        before[table][0]['name'] = after[table][0]['name'] = 'Synthetic private master'
    for name in probe.RELATIONS:
        before['relations'][name] = after['relations'][name] = [{'left_id': 41, 'right_id': 3}]
    for item in (before, after):
        item['all_field_ids'] = copy.deepcopy(item['field_ids'])
        item['all_model_ids'] = copy.deepcopy(item['model_ids'])
        item['structure_type_name_nullable'] = 'YES'
        item['category_foreign_keys'] = []
    after['structure_type_name_nullable'] = 'NO'
    after['category_foreign_keys'] = [
        ['hr_payslip_line', 'category_id', 'hr_salary_rule_category', 'id', 'n'],
        ['hr_salary_rule', 'category_id', 'hr_salary_rule_category', 'id', 'r']]
    after['all_field_ids'] += [dict(id=9000 + index, model=model, name=name)
        for index, (model, name) in enumerate(sorted(probe.NEW_FIELDS))]
    audit['database'] = 'COMMUNITY_PAYROLL_API_ADMISSION_UPGRADE_SYNTHETIC'
    audit['reload_log_lines'] = [audit['database'] + ' odoo.modules.loading: loading '
        'l10n_cl_simpledigital_payroll/' + probe.CONFIG_XML]
    return before, after, audit


class AdmissionUpgradeCase(unittest.TestCase):
    def test_period_upgrade_is_bound_to_accepted_c_without_new_fields(self):
        try:
            probe.configure_profile('period')
            self.assertEqual(probe.SOURCE_DB, 'COMMUNITY_PAYROLL_API_ADMISSION_20261029C')
            self.assertEqual(probe.SOURCE_ROOT, Path('/opt/steps-validation/community-payroll-admission-20261029C'))
            self.assertEqual(probe.VERSIONS['step_simpledigital_oca_base'], ('18.0.1.4.0', '18.0.1.5.0'))
            self.assertEqual(probe.NEW_FIELDS, set())
            self.assertEqual(probe.common.SOURCE_DB, probe.SOURCE_DB)
            self.assertEqual(legacy.SOURCE_DB, 'COMMUNITY_PAYROLL_API_CONFIGURATION_20261029D')
        finally:
            probe.configure_profile('admission')

    def test_unknown_profile_cannot_change_the_accepted_source(self):
        previous = (probe.SOURCE_DB, probe.SOURCE_ROOT, dict(probe.VERSIONS), set(probe.NEW_FIELDS))
        for name in ('CERRO_EL_PLOMO', 'period ', '', None):
            with self.assertRaises(ValueError):
                probe.configure_profile(name)
            self.assertEqual(previous, (probe.SOURCE_DB, probe.SOURCE_ROOT, probe.VERSIONS, probe.NEW_FIELDS))

    def test_already_json_and_closed_history_are_preserved_without_projection(self):
        proof = probe.verify_rows(*fixtures())
        self.assertTrue(proof['rule_json_properties_preserved_exactly'])
        self.assertEqual(proof['expected_write_date_changes'], 2)
        self.assertFalse(proof['all_original_raw_fields_exact'])
        self.assertTrue(proof['existing_relations_nonempty'])
        self.assertEqual(proof['existing_relations_preserved'], 3)
        self.assertTrue(proof['structure_type_name_not_null'])

    def test_json_text_owner_null_false_and_translation_are_not_normalized(self):
        mutations = [
            lambda row: row.update(note='<p>Nota á</p>'),
            lambda row: row.update(note={'en_US': {'en_US': '<p>Nota á</p>'}}),
            lambda row: row.update(note={'en_US': '<p>Nota a</p>'}),
            lambda row: row.update(analytic_account_id={'10': 7}),
            lambda row: row.update(analytic_account_id={'9': False}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                before, after, audit = fixtures()
                mutation(after['hr_salary_rule'][0])
                with self.assertRaises(AssertionError):
                    probe.verify_rows(before, after, audit)
        before, after, audit = fixtures()
        after['hr_salary_rule'][1]['note'] = False
        with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)
        before, after, audit = fixtures()
        after['hr_salary_rule'][0]['analytic_account_id'] = {'9': 7.0}
        with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)

    def test_closed_and_accounting_values_flags_and_timestamps_remain_strict(self):
        for table, name, value in (
            ('hr_payslip', 'paid', False), ('hr_payslip', 'step_history_locked', False),
            ('hr_payslip', 'write_date', '2026-10-29T10:05:00'),
            ('hr_payslip_line', 'total', 999), ('hr_payslip_line', 'note', {'en_US': 'changed'}),
            ('hr_payslip_line', 'analytic_account_id', {'9': 7})):
            before, after, audit = fixtures()
            after[table][0][name] = value
            with self.subTest(table=table, name=name):
                with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)
        before, after, audit = fixtures()
        before['account_move_line'] = [{'id': 101, 'debit': 12, 'credit': 0}]
        after['account_move_line'] = [{'id': 101, 'debit': 13, 'credit': 0}]
        with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)

    def test_paid_datetime_write_uid_and_added_or_removed_rows_are_not_exempt(self):
        for field in ('paid_datetime', 'write_uid'):
            before, after, audit = fixtures()
            before['hr_payslip'][0][field] = 1
            after['hr_payslip'][0][field] = 2
            with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)
        for table in probe.RAW_TABLES:
            before, after, audit = fixtures()
            after[table].append({'id': 9000})
            with self.subTest(table=table):
                with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)

    def test_all_three_relations_require_actual_nonempty_preserved_pairs(self):
        for name in probe.RELATIONS:
            before, after, audit = fixtures()
            before['relations'][name] = []
            after['relations'][name] = []
            with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)
            before, after, audit = fixtures()
            after['relations'][name] = []
            with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)

    def test_global_model_field_pk_and_numbering_cannot_change(self):
        for key in ('model_ids', 'all_model_ids', 'field_ids', 'all_field_ids'):
            before, after, audit = fixtures()
            after[key][0]['id'] += 1
            with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)
        before, after, audit = fixtures()
        after['business_sequences']['ir_sequence_007'][0] += 1
        with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)

    def test_new_field_is_reported_without_replacing_an_original(self):
        before, after, audit = fixtures()
        proof = probe.verify_rows(before, after, audit)
        self.assertEqual(len(proof['new_fields']), 5)
        after['all_field_ids'].pop()
        with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)
        before, after, audit = fixtures()
        after['all_field_ids'].append({'id': 9999, 'model': 'hr.payslip', 'name': 'unexpected_field'})
        with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)

    def test_name_not_null_and_both_category_delete_policies_are_physical(self):
        before, after, audit = fixtures()
        after['structure_type_name_nullable'] = 'YES'
        with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)
        for index in (0, 1):
            before, after, audit = fixtures()
            after['category_foreign_keys'][index][-1] = 'c'
            with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)
        before, after, audit = fixtures()
        before['hr_payroll_structure_type'][0]['name'] = None
        after['hr_payroll_structure_type'][0]['name'] = None
        with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)

    def test_json_and_historical_line_physical_types_cannot_regress(self):
        for index in range(4):
            before, after, audit = fixtures()
            after['property_columns'][index]['data_type'] = 'text_changed'
            with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)

    def test_no_timestamp_exception_without_exact_original_alias_pin_and_window(self):
        before, after, audit = fixtures()
        with self.assertRaises(AssertionError): probe.verify_rows(before, after)
        for key, value in (('approved_xml_sha256', '0' * 64), ('reload_log_lines', []),
                           ('sql_utc_after', '2026-10-29T09:00:00')):
            before, after, audit = fixtures()
            audit[key] = value
            with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)
        before, after, audit = fixtures()
        after['xml_config_aliases'][0]['noupdate'] = True
        with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)
        before, after, audit = fixtures()
        after['hr_payroll_structure'][0]['write_uid'] = 99
        with self.assertRaises(AssertionError): probe.verify_rows(before, after, audit)

    def test_offline_runtime_uses_namespace_unix_socket_and_no_service(self):
        command = probe.offline_command(Path('/private/runtime'), Path('/private/addons'), Path('/private/data'),
            'COMMUNITY_PAYROLL_API_ADMISSION_UPGRADE_TEST', Path('/private/test.log'), shell=True)
        self.assertEqual(command[:4], ['unshare', '--net', '--', 'sudo'])
        self.assertIn('--db_host=/var/run/postgresql', command)
        self.assertIn('--no-http', command)
        self.assertIn('--workers=0', command)
        self.assertIn('--max-cron-threads=0', command)
        for name in (probe.SOURCE_DB, 'karo_consultorias', 'MANAGEMENT', '', 'COMMUNITY_PAYROLL_API_ADMISSION_UPGRADE_TEST; DROP'):
            with self.assertRaises(AssertionError):
                probe.offline_command(Path('/r'), Path('/a'), Path('/d'), name, Path('/log'))
            with self.assertRaises(AssertionError):
                probe.exercise(SimpleNamespace(cr=SimpleNamespace(dbname=name)), 'seed', '/never-used')

    def test_shared_dependency_instance_does_not_reconfigure_old_regression(self):
        self.assertNotEqual(legacy.SOURCE_DB, probe.SOURCE_DB)
        self.assertEqual(legacy.SOURCE_DB, 'COMMUNITY_PAYROLL_API_CONFIGURATION_20261029D')
        self.assertEqual(probe.common.SOURCE_DB, probe.SOURCE_DB)
        self.assertEqual(probe.VERSIONS['step_payroll_oca_api'], ('18.0.1.10.0', '18.0.1.11.0'))
        self.assertEqual(probe.VERSIONS['step_simpledigital_oca_base'], ('18.0.1.3.0', '18.0.1.4.0'))

    def test_dependency_and_probe_bytes_are_sealed_and_tampering_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper, script = root / probe.HELPER_NAME, root / 'upgrade-probe.py'
            helper.write_bytes(b'private immutable helper')
            script.write_bytes(b'private probe')
            seal = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (helper, script)}
            (root / 'probe-dependencies.json').write_text(json.dumps(seal))
            with patch.object(probe, 'HELPER_PATH', helper), patch.object(probe, '__file__', str(script)):
                probe.verify_dependency(root)
                helper.write_bytes(b'changed helper')
                with self.assertRaises(AssertionError): probe.verify_dependency(root)
                helper.write_bytes(b'private immutable helper')
                script.write_bytes(b'changed probe')
                with self.assertRaises(AssertionError): probe.verify_dependency(root)


if __name__ == '__main__':
    unittest.main()
