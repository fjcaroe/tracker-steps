import json
import unittest
from unittest.mock import patch

from capture_sys_previred_stage import record_stage
from preflight_original_history_storage import sha


class SySPreservationStageTest(unittest.TestCase):
    reference = 'MANAGEMENT_QA_SYS_PREVIRED_test'
    candidate = 'COMMUNITY_SYS_PREVIRED_test'
    backup = 'a' * 64

    def snapshot(self, database, provider_field=False):
        columns = {'name': ['character varying', True]}
        if provider_field:
            columns['provider_field'] = ['text', False]
        return dict(database=database, columns={'hr_payslip_line': columns},
                    projections={'hr_payslip_line': {'rows': 3, 'sha256': 'history'}},
                    foreign_keys={}, counters={'ir_sequence_001': [18, False]})

    def record(self, database, stage, baseline=None, previous=None, provider_field=False):
        with patch('capture_sys_previred_stage.capture',
                   return_value=self.snapshot(database, provider_field)) as capture:
            receipt = record_stage(None, database, stage, self.backup, baseline, previous)
            capture.assert_called_once_with(
                None, database, json.loads(baseline)['snapshot'] if baseline else None)
        return json.dumps(receipt).encode()

    def test_restoration_and_replay_receipts_chain(self):
        baseline = self.record(self.reference, 'reference-restored')
        restored = self.record(self.candidate, 'candidate-restored', baseline)
        upgraded = self.record(self.candidate, 'candidate-upgraded', baseline, restored, True)
        rolled_back = self.record(self.candidate, 'candidate-rolled-back', baseline, upgraded, True)
        outcome = json.loads(rolled_back)
        self.assertTrue(outcome['preserved'])
        self.assertEqual(outcome['baseline_sha256'], sha(baseline))
        self.assertEqual(outcome['previous_sha256'], sha(upgraded))

    def test_restore_with_added_column_blocks_next_stage(self):
        baseline = self.record(self.reference, 'reference-restored')
        restored = self.record(self.candidate, 'candidate-restored', baseline, provider_field=True)
        outcome = json.loads(restored)
        self.assertFalse(outcome['preserved'])
        self.assertEqual(outcome['differences']['added_columns'], ['hr_payslip_line.provider_field'])
        with self.assertRaisesRegex(ValueError, 'previous-stage-mismatch'):
            self.record(self.candidate, 'candidate-upgraded', baseline, restored)

    def test_changed_backup_or_candidate_cannot_continue_chain(self):
        baseline = self.record(self.reference, 'reference-restored')
        restored = self.record(self.candidate, 'candidate-restored', baseline)
        with self.assertRaisesRegex(ValueError, 'reference-receipt-mismatch'):
            record_stage(None, self.candidate, 'candidate-upgraded', 'b' * 64, baseline, restored)
        with self.assertRaisesRegex(ValueError, 'previous-stage-mismatch'):
            record_stage(None, self.candidate + '_other', 'candidate-upgraded', self.backup,
                         baseline, restored)
