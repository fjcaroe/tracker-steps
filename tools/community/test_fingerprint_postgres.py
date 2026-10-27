"""Exercise the real fingerprint SQL with session-local PostgreSQL fixtures only."""
import argparse
import json
import re
import unittest
from unittest.mock import patch

import validate_finance_foundation as validation


class FingerprintCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        queries = []

        def capture(database, query):
            queries.append(query)
            return 'normalization_fixture' if len(queries) == 1 else '{}'

        with patch.object(validation, 'sql', side_effect=capture):
            validation.snapshot('unused')
        cls.query = queries[-1]

    def digest(self, amount, label='same'):
        # Values come only from the literal fixtures below, never user input.
        statement = ('CREATE TEMP TABLE normalization_fixture (amount numeric,label text); '
                     "INSERT INTO normalization_fixture VALUES (%s,'%s'); " % (amount, label) + self.query)
        return json.loads(validation.sql(self.database, statement))['normalization_fixture']

    def test_fractional_trailing_zeroes_are_equivalent_and_auditable(self):
        before, after = self.digest('15.00'), self.digest('15')
        self.assertEqual(before['hash'], after['hash'])
        self.assertNotEqual(before['representation_hash'], after['representation_hash'])
        self.assertTrue(validation.same_values({'fixture': before}, {'fixture': after}))

    def test_small_exact_fraction_is_not_rounded_away(self):
        before, after = self.digest('15.00'), self.digest('15.000000000000000000000001')
        self.assertNotEqual(before['hash'], after['hash'])
        self.assertFalse(validation.same_values({'fixture': before}, {'fixture': after}))

    def test_numeric_looking_strings_remain_distinct(self):
        self.assertNotEqual(self.digest('15', '15.00')['hash'], self.digest('15', '15')['hash'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'(COMMUNITY_FOUNDATION_|MANAGEMENT_QA_CERRO_COMMUNITY_)[A-Za-z0-9_]+', args.database)
    FingerprintCase.database = args.database
    unittest.main(argv=['fingerprint'], verbosity=2)
