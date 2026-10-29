"""Isolated registry metadata fixtures. No Odoo, records, database or keys."""
import copy
import json
from types import SimpleNamespace
import unittest

import caf_registry_contract as contract


class Poison:
    def __repr__(self):
        raise AssertionError('A default/secret was rendered')


class Cursor:
    dbname = 'MANAGEMENT_QA_CERRO_SYNTHETIC'
    def __init__(self, read_only='on'):
        self.read_only, self.statements = read_only, []
    def execute(self, statement):
        if statement != 'SHOW transaction_read_only':
            raise AssertionError('Unexpected SQL or record access')
        self.statements.append(statement)
    def fetchone(self):
        return (self.read_only,)


class Env:
    def __init__(self, model):
        self.cr = Cursor()
        self.registry = SimpleNamespace(db_name=self.cr.dbname, ready=True,
                                         models={contract.MODEL: model})
    def __getitem__(self, key):
        raise AssertionError('ORM record/model access is forbidden')


def compute_never_called(*args, **kwargs):
    raise AssertionError('Compute/provider code executed')


def field(**changes):
    data = dict(type='binary', attachment=True, store=True, required=False,
                readonly=False, related=None, groups=None, compute=False)
    data.update(changes)
    return SimpleNamespace(**data)


def model():
    class Provider:
        _name = contract.MODEL
        _module = 'synthetic_caf_provider'
        _table = contract.TABLE
        _auto = True
        _transient = False
        _fields = {'caf_file': field(), 'company_id': field(type='many2one',
                    readonly=True, compute=compute_never_called, groups='account.group_account_manager')}
        def method(self, first, /, second=Poison(), *args, option=Poison(), **kwargs):
            raise AssertionError('Provider code executed')
        @staticmethod
        def static_method(argument=Poison()):
            raise AssertionError('Static provider code executed')
        @classmethod
        def class_method(cls, argument=Poison()):
            raise AssertionError('Class provider code executed')
        @property
        def protected_property(self):
            raise AssertionError('A descriptor was executed')
    return Provider


class CAFRegistryContractCase(unittest.TestCase):
    def assert_code(self, code, env):
        with self.assertRaisesRegex(contract.RegistryContractError, '^' + code + '$'):
            contract.inspect_registry(env)

    def test_binary_policy_is_metadata_not_adoption(self):
        result = contract.inspect_registry(Env(model()))
        self.assertTrue(result['binary_attachment_policy_proven'])
        self.assertFalse(result['adoption_ready'])
        self.assertFalse(result['folio_allocation_ready'])
        self.assertFalse(result['payload_storage_preservation_verified'])
        self.assertFalse(result['provider_methods_called'])

    def test_only_show_read_only_is_executed_and_no_records_accessed(self):
        env = Env(model())
        contract.inspect_registry(env)
        self.assertEqual(env.cr.statements, ['SHOW transaction_read_only'])

    def test_production_and_qa_are_rejected_before_any_sql(self):
        for database in ('CERRO_EL_PLOMO', 'SyS', 'karo_consultorias', 'QA_CERROELPLOMO'):
            with self.subTest(database=database):
                env = Env(model()); env.cr.dbname = database; env.registry.db_name = database
                self.assert_code('private-database-required', env)
                self.assertEqual(env.cr.statements, [])

    def test_read_write_transaction_is_rejected(self):
        env = Env(model()); env.cr.read_only = 'off'
        self.assert_code('read-only-transaction-required', env)

    def test_registry_must_be_loaded_and_match_cursor(self):
        env = Env(model()); env.registry.ready = False
        self.assert_code('registry-not-loaded', env)
        self.assertEqual(env.cr.statements, [])
        env = Env(model()); env.registry.db_name = 'OTHER_DATABASE'
        self.assert_code('registry-database-mismatch', env)
        self.assertEqual(env.cr.statements, [])

    def test_missing_caf_model_is_not_fabricated(self):
        env = Env(model()); env.registry.models = {}
        self.assert_code('caf-model-missing', env)
        self.assertEqual(env.registry.models, {})

    def test_identity_auto_and_transient_cannot_be_substituted(self):
        for attribute, value in (('_table', 'parallel_caf'), ('_auto', False), ('_transient', True)):
            provider = model(); setattr(provider, attribute, value)
            with self.subTest(attribute=attribute):
                self.assert_code('caf-model-identity-mismatch', Env(provider))

    def test_field_metadata_is_reported_without_running_compute(self):
        result = contract.inspect_registry(Env(model()))
        company = result['fields']['company_id']
        self.assertTrue(company['readonly'])
        self.assertEqual(company['groups'], 'account.group_account_manager')
        self.assertTrue(company['compute'].endswith('.compute_never_called'))

    def test_parameters_preserve_kinds_without_defaults_or_body(self):
        result = contract.inspect_registry(Env(model()))
        methods = {row['name']: row for row in result['providers'][0]['methods']}
        self.assertEqual(methods['method']['signatures'][0]['parameters'], [
            {'name': 'self', 'kind': 'POSITIONAL_ONLY'},
            {'name': 'first', 'kind': 'POSITIONAL_ONLY'},
            {'name': 'second', 'kind': 'POSITIONAL_OR_KEYWORD'},
            {'name': 'args', 'kind': 'VAR_POSITIONAL'},
            {'name': 'option', 'kind': 'KEYWORD_ONLY'},
            {'name': 'kwargs', 'kind': 'VAR_KEYWORD'}])
        self.assertNotIn('protected_property', methods)
        self.assertEqual(methods['static_method']['kind'], 'static')
        self.assertEqual(methods['class_method']['kind'], 'class')
        self.assertNotIn('Poison', json.dumps(result))

    def test_provider_mro_lists_extension_methods_but_not_generic_base(self):
        parent = model()
        class Extension(parent):
            _inherit = contract.MODEL
            def extension_method(self, value):
                raise AssertionError('Extension executed')
        result = contract.inspect_registry(Env(Extension))
        self.assertEqual(len(result['providers']), 2)
        self.assertEqual(result['providers'][0]['methods'][0]['name'], 'extension_method')

    def test_wrapped_signatures_are_passive_and_cycles_bounded(self):
        provider = model()
        def wrapper(self, *args, **kwargs):
            raise AssertionError('Wrapper executed')
        wrapper.__wrapped__ = provider.method
        provider.wrapper = wrapper
        result = contract.inspect_registry(Env(provider))
        row = next(row for row in result['providers'][0]['methods'] if row['name'] == 'wrapper')
        self.assertEqual(len(row['signatures']), 2)
        self.assertFalse(row['wrapper_chain_incomplete'])
        wrapper.__wrapped__ = wrapper
        result = contract.inspect_registry(Env(provider))
        row = next(row for row in result['providers'][0]['methods'] if row['name'] == 'wrapper')
        self.assertEqual(len(row['signatures']), 1)
        self.assertTrue(row['wrapper_chain_incomplete'])

    def test_binary_column_or_unstored_field_does_not_prove_attachment_policy(self):
        for change in ({'attachment': False}, {'store': False}, {'type': 'char'}):
            provider = model(); provider._fields['caf_file'] = field(**change)
            with self.subTest(change=change):
                self.assertFalse(contract.inspect_registry(Env(provider))['binary_attachment_policy_proven'])

    def test_related_path_is_metadata_only_and_registry_unchanged(self):
        provider = model(); provider._fields['company_id'].related = ('owner_id', 'company_id')
        before = copy.copy(provider._fields)
        env = Env(provider); result = contract.inspect_registry(env)
        self.assertEqual(result['fields']['company_id']['related'], ['owner_id', 'company_id'])
        self.assertEqual(provider._fields, before)
        self.assertIs(env.registry.models[contract.MODEL], provider)


if __name__ == '__main__':
    unittest.main(verbosity=2)
