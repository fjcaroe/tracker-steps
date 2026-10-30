"""Pure first-load storage gate tests; no database, ORM or monetary fixture."""
from copy import deepcopy
import json
import unittest

import preflight_original_history_storage as gate


def database(mode):
    return {'cold-community': 'COMMUNITY_PAYROLL_API_STORAGE_TEST',
        'anchored': 'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_STORAGE_TEST',
        'native': 'MANAGEMENT_QA_CERRO_PAYROLL_API_NATIVE_STORAGE_TEST'}[mode]


def snapshot(mode, *, absent=False):
    metadata = {}
    for index, (table, (field, pg_name, sql_type)) in enumerate(gate.TABLES.items(), 1):
        metadata[table] = None if absent else {'schema': 'public', 'table': table, 'kind': 'r', 'oid': index,
            'columns': [{'name': field, 'sql_type': sql_type, 'type_name': pg_name,
                'type_oid': 23 if pg_name == 'int4' else 1043, 'type_modifier': -1,
                'not_null': True, 'has_default': False, 'identity': '', 'generated': ''}]}
    return {'database': database(mode), 'transaction_read_only': 'on', 'transaction_isolation': 'repeatable read',
        'primary': True, 'metadata': metadata}


class Callback:
    def __init__(self, discovery, final=None, *, rows=0):
        self.calls = []
        self.discovery = deepcopy(discovery)
        self.final = deepcopy(final if final is not None else discovery)
        self.final['null_counts'] = {table: None if value is None else {'rows': rows, 'null_rows': 0}
            for table, value in self.final['metadata'].items()}

    def __call__(self, database, query):
        self.calls.append((database, query))
        return json.dumps(self.discovery if len(self.calls) == 1 else self.final)


class OriginalHistoryStorageCase(unittest.TestCase):
    def test_empty_cold_database_is_admitted_without_parsing_missing_history_tables(self):
        mode = 'cold-community'; callback = Callback(snapshot(mode, absent=True))
        receipt = gate.capture(callback, database(mode), mode)
        self.assertEqual(receipt['observed']['tables_present'], [])
        self.assertEqual(receipt['observed']['tables_absent_cold_only'], list(gate.TABLES))
        self.assertEqual(len(callback.calls), 2)
        self.assertNotIn('FROM public.hr_payslip)', callback.calls[1][1])
        self.assertNotIn('FROM public.hr_payslip_line)', callback.calls[1][1])
        self.assertEqual(receipt['snapshot']['null_counts'], {'hr_payslip': None, 'hr_payslip_line': None})

    def test_actual_existing_native_and_anchor_contracts_require_original_not_null(self):
        for mode in ('native', 'anchored'):
            callback = Callback(snapshot(mode), rows=10)
            receipt = gate.capture(callback, database(mode), mode)
            self.assertTrue(receipt['actual_readonly'])
            self.assertTrue(receipt['observed']['company_source_not_null_required'])
            self.assertEqual(receipt['observed']['null_counts']['hr_payslip_line'], {'rows': 10, 'null_rows': 0})
            for table in gate.TABLES:
                altered = snapshot(mode); altered['metadata'][table] = None
                with self.subTest(mode=mode, table=table), self.assertRaises(ValueError):
                    gate.capture(Callback(altered), database(mode), mode)
            altered = snapshot(mode); altered['metadata']['hr_payslip']['columns'][0]['not_null'] = False
            with self.assertRaises(ValueError): gate.capture(Callback(altered), database(mode), mode)

    def test_existing_cold_company_can_be_nullable_but_null_rows_always_block_backfill(self):
        mode = 'cold-community'; original = snapshot(mode)
        original['metadata']['hr_payslip']['columns'][0]['not_null'] = False
        callback = Callback(original)
        receipt = gate.capture(callback, database(mode), mode)
        self.assertFalse(receipt['observed']['company_source_not_null_required'])
        for table in gate.TABLES:
            callback = Callback(original, rows=2); callback.final['null_counts'][table]['null_rows'] = 1
            with self.subTest(table=table), self.assertRaisesRegex(ValueError, 'null-blocks-first-initialization'):
                gate.capture(callback, database(mode), mode)

    def test_jsonb_line_is_rejected_even_empty_before_any_count_query(self):
        for mode in gate.MODES:
            original = snapshot(mode)
            column = original['metadata']['hr_payslip_line']['columns'][0]
            column.update(sql_type='jsonb', type_name='jsonb', type_oid=3802)
            callback = Callback(original)
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'original-column-type'):
                gate.capture(callback, database(mode), mode)
            self.assertEqual(len(callback.calls), 1)

    def test_wrong_company_type_nullable_line_missing_generated_or_computed_storage_reject(self):
        for mutation in ('company_type', 'line_nullable', 'missing', 'identity', 'generated', 'bounded_varchar'):
            mode = 'native'; original = snapshot(mode)
            company = original['metadata']['hr_payslip']['columns'][0]
            line = original['metadata']['hr_payslip_line']['columns'][0]
            if mutation == 'company_type': company.update(sql_type='bigint', type_name='int8', type_oid=20)
            if mutation == 'line_nullable': line['not_null'] = False
            if mutation == 'missing': original['metadata']['hr_payslip']['columns'] = []
            if mutation == 'identity': company['identity'] = 'a'
            if mutation == 'generated': line['generated'] = 's'
            if mutation == 'bounded_varchar': line.update(sql_type='character varying(10)', type_modifier=14)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                gate.capture(Callback(original), database(mode), mode)

    def test_final_catalog_and_counts_are_atomic_and_changed_discovery_cannot_be_combined(self):
        for mutation in ('new_table', 'dropped_table', 'recreated_oid', 'nullable', 'rw', 'isolation'):
            mode = 'cold-community'; before = snapshot(mode, absent=mutation == 'new_table'); after = deepcopy(before)
            if mutation == 'new_table': after = snapshot(mode)
            if mutation == 'dropped_table': after['metadata']['hr_payslip_line'] = None
            if mutation == 'recreated_oid': after['metadata']['hr_payslip']['oid'] = 999
            if mutation == 'nullable': after['metadata']['hr_payslip']['columns'][0]['not_null'] = False
            if mutation == 'rw': after['transaction_read_only'] = 'off'
            if mutation == 'isolation': after['transaction_isolation'] = 'read committed'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                gate.capture(Callback(before, after), database(mode), mode)

    def test_wrong_prefix_or_mode_never_calls_sql_and_receipts_are_sealed_to_query_mode(self):
        for mode, name in [('native', 'SyS'), ('anchored', 'CERRO_EL_PLOMO'),
                ('cold-community', database('native')), ('native', database('anchored')), ('other', 'COMMUNITY_PAYROLL_API_TEST')]:
            calls = []
            with self.subTest(mode=mode, name=name), self.assertRaises(ValueError):
                gate.capture(lambda *args: calls.append(args), name, mode)
            self.assertEqual(calls, [])
        mode = 'native'; receipt = gate.capture(Callback(snapshot(mode)), database(mode), mode)
        for key, value in [('capture_query_sha256', '0' * 64), ('discovery_query_sha256', '0' * 64),
                ('payroll_values_read', True), ('database_writes', True), ('before_candidate_initialization_contract', False),
                ('initializer_chronology_proven_by_helper', True)]:
            altered = deepcopy(receipt); altered[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): gate.verify(altered, database(mode), mode)

    def test_supplied_sql_contains_only_catalogs_counts_and_null_predicates_in_ro_transactions(self):
        mode = 'anchored'; callback = Callback(snapshot(mode))
        gate.capture(callback, database(mode), mode)
        for db, query in callback.calls:
            self.assertEqual(db, database(mode))
            self.assertTrue(query.startswith('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'))
            self.assertTrue(query.endswith('ROLLBACK;'))
            self.assertNotRegex(query.upper(), r'\b(UPDATE|DELETE|INSERT|ALTER|CREATE|DROP|NEXTVAL|SETVAL)\b')
            self.assertNotRegex(query, r'\b(amount|wage|total|debit|credit|formula)\b')
        self.assertIn('count(*) FILTER (WHERE company_id IS NULL)', callback.calls[1][1])
        self.assertIn('count(*) FILTER (WHERE name IS NULL)', callback.calls[1][1])
        self.assertIn('c.oid::bigint', callback.calls[1][1])


if __name__ == '__main__':
    unittest.main()
