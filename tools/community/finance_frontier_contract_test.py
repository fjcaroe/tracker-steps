"""Fail-closed checks for exact banking identity, flags and source audit."""
import copy
import unittest

from finance_frontier_contract import LEGACY_XMLIDS, verify_metadata


class FinanceMetadataContractTest(unittest.TestCase):
    def snapshots(self):
        ids = [{'id': i + 1, 'module': module, 'name': name, 'model': 'ir.model.fields',
                'res_id': 100 + i, 'noupdate': bool(i % 2)}
               for i, (module, name) in enumerate((module, name)
                   for module, names in LEGACY_XMLIDS.items() for name in names)]
        views = [{'id': i, 'model': 'res.partner.bank', 'inherit_id': 7, 'active': True,
                  'arch_db': {'en_US': '<data><field name="bank_id"/></data>'},
                  'arch_fs': 'legacy/views/bank.xml', 'arch_prev': None, 'arch_updated': False}
                 for i in (40, 41)]
        before = {'xmlids': ids, 'views': views}
        after = copy.deepcopy(before)
        for row in after['views']:
            row['arch_fs'] = 'step_bank_export_core/views/res_partner_bank_views.xml'
            row['arch_prev'] = row['arch_db']['en_US']
        return before, after

    def test_exact_original_flags_and_native_source_audit_pass(self):
        before, after = self.snapshots()
        self.assertEqual(verify_metadata(before, after)['original_xmlids_preserved'], 15)
        self.assertTrue(verify_metadata(before, after)['original_noupdate_exact'])

    def test_replacing_an_original_xmlid_record_is_rejected(self):
        before, after = self.snapshots()
        after['xmlids'][0]['id'] += 1000
        with self.assertRaises(AssertionError):
            verify_metadata(before, after)

    def test_redirecting_original_identifier_is_rejected(self):
        before, after = self.snapshots()
        after['xmlids'][0]['res_id'] += 1
        with self.assertRaises(AssertionError):
            verify_metadata(before, after)
        for index in (0, 1):
            before, after = self.snapshots()
            after['xmlids'][index]['noupdate'] = not before['xmlids'][index]['noupdate']
            with self.assertRaises(AssertionError):
                verify_metadata(before, after)

    def test_view_architecture_or_active_state_cannot_hide_in_audit_allowance(self):
        for key, value in [('arch_db', {'en_US': '<data/>'}), ('active', False), ('inherit_id', 8)]:
            before, after = self.snapshots()
            after['views'][0][key] = value
            with self.assertRaises(AssertionError):
                verify_metadata(before, after)

    def test_undeclared_source_or_previous_architecture_is_rejected(self):
        for key, value in [('arch_fs', 'other/views/fake.xml'), ('arch_prev', '<new/>')]:
            before, after = self.snapshots()
            after['views'][0][key] = value
            with self.assertRaises(AssertionError):
                verify_metadata(before, after)


if __name__ == '__main__':
    unittest.main()
