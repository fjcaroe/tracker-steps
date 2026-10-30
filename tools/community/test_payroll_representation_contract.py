"""Exact lexical custody negatives, with synthetic package types only."""
from copy import deepcopy
import unittest

import payroll_representation_contract as contract


def fixture():
    before = ['{"id": %s, "name": "same", "weight": 15.00, "nullable": null}' % ident for ident in range(1, 6)]
    after = [row.replace('15.00', '15') for row in before]
    first = {'rows': 5, 'hash': 'same-exact-value-fingerprint', 'representation_hash': contract.raw_hash(before)}
    last = dict(first, representation_hash=contract.raw_hash(after))
    proof = {'schema': 1, 'table': contract.TABLE, 'read_only': True, 'database_writes': False,
        'before_rows_json': before, 'after_rows_json': after}
    return first, last, last, proof


class RepresentationContractCase(unittest.TestCase):
    def test_all_five_raw_rows_are_bound_and_only_trailing_numeric_zeros_admitted(self):
        values = fixture()
        result = contract.verify(*values)
        self.assertTrue(result['values_equal'])
        self.assertFalse(result['raw_representation_equal'])
        self.assertEqual(len(result['fractional_numeric_zero_changes']), 5)
        self.assertFalse(result['float_or_rounding_used'])
        changed = deepcopy(values)
        changed[3]['after_rows_json'][0] += ' '
        with self.assertRaisesRegex(contract.RepresentationError, 'fingerprint'):
            contract.verify(*changed)

    def test_tiny_fraction_text_null_id_and_other_table_cannot_be_classified(self):
        for old, new in (('15', '15.000000000000000000000001'), ('"same"', '"different"'),
                ('null', '0'), ('"id": 1', '"id": 6')):
            first, upgraded, after, proof = fixture()
            proof['after_rows_json'][0] = proof['after_rows_json'][0].replace(old, new)
            upgraded = after = dict(after, representation_hash=contract.raw_hash(proof['after_rows_json']))
            with self.assertRaises(contract.RepresentationError):
                contract.verify(first, upgraded, after, proof)
        values = fixture()
        values[3]['table'] = 'account_move'
        with self.assertRaisesRegex(contract.RepresentationError, 'unapproved'):
            contract.verify(*values)

    def test_representation_of_nested_numbers_and_during_tests_cannot_be_ignored(self):
        first, upgraded, after, proof = fixture()
        proof['before_rows_json'] = [row.replace('"same"', '{"nested": 1.00}') for row in proof['before_rows_json']]
        proof['after_rows_json'] = [row.replace('"same"', '{"nested": 1}') for row in proof['after_rows_json']]
        first['representation_hash'] = contract.raw_hash(proof['before_rows_json'])
        upgraded = after = dict(after, representation_hash=contract.raw_hash(proof['after_rows_json']))
        with self.assertRaisesRegex(contract.RepresentationError, 'nonnumeric byte'):
            contract.verify(first, upgraded, after, proof)
        first, upgraded, after, proof = fixture()
        with self.assertRaisesRegex(contract.RepresentationError, 'during tests'):
            contract.verify(first, dict(upgraded, representation_hash='different'), after, proof)


if __name__ == '__main__':
    unittest.main()
