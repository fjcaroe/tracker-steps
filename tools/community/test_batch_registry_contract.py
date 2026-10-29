import unittest
from types import SimpleNamespace

from batch_registry_contract import MODEL, inspect_registry


class Cursor:
    dbname = 'MANAGEMENT_QA_CERRO_TEST'

    def __init__(self, readonly='on'):
        self.readonly = readonly

    def execute(self, query):
        assert query == 'SHOW transaction_read_only'

    def fetchone(self):
        return (self.readonly,)


class Env:
    def __init__(self, readonly='on', present=False):
        self.cr = Cursor(readonly)
        self.registry = {MODEL: True} if present else {}

    def __getitem__(self, key):
        assert key == MODEL
        return SimpleNamespace(_name=MODEL, _table='account_batch_payment', _auto=True, _transient=False,
                               _fields={'amount': SimpleNamespace(type='monetary', store=True,
                                   required=False, readonly=True, currency_field='currency_id')})


class BatchRegistryContractCase(unittest.TestCase):
    def test_writable_registry_is_rejected_before_accessing_models(self):
        with self.assertRaises(ValueError):
            inspect_registry(Env(readonly='off'))

    def test_missing_model_is_reported_without_a_stub(self):
        proof = inspect_registry(Env())
        self.assertFalse(proof['model_present'])
        self.assertFalse(proof['functional_provider_certified'])

    def test_field_metadata_does_not_read_records_or_certify_calculation(self):
        proof = inspect_registry(Env(present=True))
        self.assertEqual(proof['fields']['amount']['currency_field'], 'currency_id')
        self.assertFalse(proof['business_records_read'])
        self.assertFalse(proof['computes_executed'])


if __name__ == '__main__':
    unittest.main()
