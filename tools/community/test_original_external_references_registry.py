"""Isolation guards: fake metadata, never ORM records or a database."""
from types import SimpleNamespace
import unittest

import original_external_references_registry as audit


class Cursor:
    def __init__(self, database='COMMUNITY_PAYROLL_API_SYNTHETIC', mode='on'):
        self.dbname, self.mode, self.calls = database, mode, []
    def execute(self, query):
        self.calls.append(query)
    def fetchone(self):
        return (self.mode,)


class RegistryCase(unittest.TestCase):
    def env(self, **options):
        def forbidden(*args):
            raise AssertionError('Callable field selection must not execute')
        field = SimpleNamespace(type='reference', store=True, selection=forbidden)
        many = SimpleNamespace(type='many2many', store=True, comodel_name='hr.payroll.structure.type',
            relation='explicit_actual_relation', column1='owner_pk', column2='type_pk')
        model = SimpleNamespace(_table='custom_actual_table', _auto=True, _abstract=False,
            _transient=False, _inherits={}, _fields={'target': field, 'type_ids': many})
        return SimpleNamespace(cr=Cursor(**options), registry=SimpleNamespace(models={'custom.owner': model}))

    def test_binding_uses_actual_registry_table_and_m2m_columns_without_calling_selection(self):
        env = self.env()
        result = audit.inspect_registry(env, source_packet_sha256='1' * 64, acceptance_sha256='2' * 64)
        self.assertEqual(env.cr.calls, ['SHOW transaction_read_only'])
        model = result['models'][0]
        self.assertEqual(model['table'], 'custom_actual_table')
        row = next(row for row in model['fields'] if row['type'] == 'many2many')
        self.assertEqual((row['relation_table'], row['column1'], row['column2']),
            ('explicit_actual_relation', 'owner_pk', 'type_pk'))
        self.assertTrue(model['fields'][0]['selection_callable'])
        for flag in ('orm_records_accessed', 'source_bodies_read', 'callables_executed', 'database_writes', 'adoption_authorized'):
            self.assertFalse(result[flag])

    def test_production_readwrite_or_unsealed_payload_rejected_before_metadata(self):
        for env, pin in ((self.env(database='CERROELPLOMO'), '1' * 64),
                         (self.env(mode='off'), '1' * 64), (self.env(), 'not a hash')):
            with self.assertRaises(ValueError):
                audit.inspect_registry(env, source_packet_sha256=pin, acceptance_sha256='2' * 64)


if __name__ == '__main__':
    unittest.main()
