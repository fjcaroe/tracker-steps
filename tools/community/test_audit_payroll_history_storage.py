"""Readonly boundaries, exact storage mismatches and separate identity profiles."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import audit_payroll_history_storage as audit


def fixture():
    fields, columns, models = [], [], []
    for index, (model, table, name, kind, required, translate) in enumerate(audit.SPECS, 1):
        fields.append({'id': index, 'model': model, 'name': name, 'ttype': 'many2one' if kind == 'int4' else 'char',
            'required': required, 'translate': translate, 'store': True})
        columns.append({'table_name': table, 'column_name': name, 'typname': kind, 'typmod': -1,
            'not_null': required, 'has_default': False})
        models.append({'id': index + 10, 'model': model, 'state': 'base'})
    return {'fields': fields, 'columns': columns, 'models': models, 'field_xmlids': [],
        'transaction': [{'database': 'COMMUNITY_PAYROLL_API_STORAGE_PRIVATE'}],
        'calendar_fk': [{'conname': 'hr_contract_resource_calendar_id_fkey', 'confdeltype': 'n',
            'confupdtype': 'a', 'convalidated': True, 'condeferrable': False, 'condeferred': False,
            'referenced_table': 'resource_calendar', 'referenced_column': 'id'}]}


class StorageAuditCase(unittest.TestCase):
    def test_queries_read_catalogs_only_and_command_forces_readonly_after_sudo(self):
        value = audit.payload()
        self.assertTrue(value.startswith('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'))
        self.assertTrue(value.endswith('ROLLBACK;'))
        for forbidden in ('FROM hr_contract ', 'FROM hr_payslip ', 'FROM hr_payslip_line ', 'FROM hr_salary_rule ',
            'FROM hr_payslip_worked_days ', 'nextval(', 'setval(', 'UPDATE ', 'INSERT ', 'SELECT *'):
            self.assertNotIn(forbidden, value)
        args = audit.command('COMMUNITY_PAYROLL_API_STORAGE_PRIVATE')
        self.assertLess(args.index('postgres'), args.index('/usr/bin/env'))
        self.assertIn('-i', args)
        self.assertIn('PGOPTIONS=-c default_transaction_read_only=on', args)
        self.assertIn('PGPASSFILE=/dev/null', args)
        self.assertIn('--no-password', args)
        for database in ('SyS', 'karo_consultorias', 'CERRO_EL_PLOMO', 'postgres', 'COMMUNITY_PAYROLL_API_X;DROP'):
            with patch.object(audit.subprocess, 'run') as called, self.assertRaises(ValueError):
                audit.snapshot(database)
            called.assert_not_called()

    def test_each_observed_mismatch_remains_visible_without_a_waiver(self):
        data = fixture()
        result = audit.assess(data)
        self.assertTrue(result['all_four_catalog_contracts_match'])
        self.assertEqual(result['catalog_contracts_closed'], 4)
        for index in range(4):
            changed = deepcopy(data)
            changed['columns'][index]['typname'] = 'float8'
            self.assertEqual(audit.assess(changed)['catalog_contracts_closed'], 3)
        for index in (2, 3):
            changed = deepcopy(data); changed['columns'][index]['not_null'] = True
            self.assertFalse(audit.assess(changed)['all_four_catalog_contracts_match'])
        for change in ('confdeltype', 'referenced_table', 'convalidated'):
            changed = deepcopy(data); changed['calendar_fk'][0][change] = {'confdeltype': 'r',
                'referenced_table': 'hr_employee', 'convalidated': False}[change]
            self.assertFalse(audit.assess(changed)['calendar_fk_set_null'])
        self.assertEqual(result['other_columns_waived'], [])
        self.assertFalse(result['adoption_authorized'])
        self.assertIsNone(result['runtime_metadata_match'])

    def test_transport_demands_every_section_and_actual_readonly_transaction(self):
        data = {key: [] for key in audit.queries()}
        data['transaction'] = [{'database': 'COMMUNITY_PAYROLL_API_STORAGE_PRIVATE', 'read_only': 'on',
            'default_read_only': 'on', 'isolation': 'repeatable read'}]
        lines = [json.dumps({'section': key, 'rows': value}) for key, value in data.items()]
        output = '\n'.join(lines)
        for body, valid in ((output, True), ('\n'.join(lines[:-1]), False),
            (output + '\n' + lines[0], False), (output.replace('"on"', '"off"'), False)):
            with patch.object(audit.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=body)):
                if valid:
                    self.assertEqual(audit.snapshot('COMMUNITY_PAYROLL_API_STORAGE_PRIVATE'), data)
                else:
                    with self.assertRaises(ValueError): audit.snapshot('COMMUNITY_PAYROLL_API_STORAGE_PRIVATE')

    def test_registry_observer_reads_no_records_and_checks_actual_cursor_first(self):
        class Cursor:
            dbname = 'COMMUNITY_PAYROLL_API_STORAGE_PRIVATE'
            readonly = True
            def execute(self, value):
                self.statement = value
            def fetchone(self):
                return ('on',)
        class Registry(dict):
            db_name = Cursor.dbname
            ready = True
        registry = Registry()
        for model, table, name, kind, required, translate in audit.SPECS:
            field = SimpleNamespace(model_name=model, name=name, type='many2one' if kind == 'int4' else 'char',
                required=required, translate=translate, store=True, column_type=(kind, kind),
                related=None, compute=None, groups=None, comodel_name='resource.calendar' if kind == 'int4' else None,
                ondelete='set null' if kind == 'int4' else None)
            registry[model] = SimpleNamespace(_table=table, _auto=True, _transient=False, _fields={name: field})
        env = SimpleNamespace(cr=Cursor(), registry=registry)
        result = audit.inspect_registry(env)
        self.assertEqual(env.cr.statement, 'SHOW transaction_read_only')
        self.assertFalse(result['records_read'])
        self.assertTrue(audit.assess(fixture(), result)['runtime_metadata_match'])
        mismatched = deepcopy(result); mismatched['database'] += '_OTHER'
        with self.assertRaises(ValueError): audit.assess(fixture(), mismatched)
        changed = deepcopy(result); changed['fields'][0]['column_type'] = ['jsonb', 'jsonb']
        self.assertFalse(audit.assess(fixture(), changed)['runtime_metadata_match'])
        env.cr.readonly = False
        with self.assertRaises(ValueError): audit.inspect_registry(env)
        env.cr.readonly = True; env.cr.dbname = 'SyS'
        with self.assertRaises(ValueError): audit.inspect_registry(env)

    def test_normal_installation_never_claims_original_identity_but_anchor_reports_collision(self):
        data = fixture()
        def report(profile, metadata):
            return {'profile': profile, 'database': 'PRIVATE', 'read_only': True, 'database_writes': False,
                'metadata_before': metadata, 'metadata_after': deepcopy(metadata)}
        source = report('native-reference', data)
        changed = deepcopy(data); changed['fields'][0]['id'] += 100
        normal = audit.compare(source, report('normal-community', changed))
        self.assertTrue(normal['four_column_contracts_equal'])
        self.assertIsNone(normal['anchored_original_metadata_identity'])
        self.assertFalse(normal['normal_installation_identity_equivalence_claimed'])
        anchored = audit.compare(source, report('anchored-community', changed))
        self.assertFalse(anchored['anchored_original_metadata_identity']['fields'])
        unstable = report('anchored-community', data); unstable['metadata_after']['fields'].pop()
        with self.assertRaises(ValueError): audit.compare(source, unstable)
        with self.assertRaises(ValueError): audit.compare(source, source)

    def test_real_provider_wrappers_are_discoverable_and_never_compute_a_paid_fixture(self):
        root = Path(__file__).resolve().parents[2]
        for file in ('step_payroll_oca_api/tests/test_original_history_storage.py',
                     'step_payroll_enterprise_reference/tests/test_native_history_storage.py'):
            tree = ast.parse((root / file).read_text())
            methods = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
            self.assertEqual(len(methods), 5)
        tree = ast.parse((root / 'step_payroll_contracts/history_storage_testing.py').read_text())
        forbidden = {'compute_sheet', 'action_payslip_done', 'action_payslip_paid'}
        self.assertFalse({node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} & forbidden)
        sudo_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == 'sudo']
        self.assertTrue(all(len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
            and node.args[0].value is False for node in sudo_calls))


if __name__ == '__main__':
    unittest.main()
