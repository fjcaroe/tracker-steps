"""Safety tests for cleanup_retired_filestores; no live server or database access."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

if os.name == 'nt':
    # The production CLI is Linux-only; pure validation also runs on Windows.
    sys.modules.setdefault('fcntl', types.SimpleNamespace())

import cleanup_retired_filestores as cleanup


class CleanupSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(patch.stopall)
        patch.object(cleanup, 'ROOT', self.root).start()
        patch.object(cleanup, 'mount_paths', return_value=[]).start()
        self.database = 'MANAGEMENT_QA_CERRO_t171f'
        self.stage = self.root / 'management_cerro_t171f'
        self.path = self.stage / 'data/filestore' / self.database
        self.path.mkdir(parents=True)
        (self.path / 'ab').mkdir()
        (self.path / 'ab/attachment').write_bytes(b'attachment')
        self.source = self.stage / 'source.dump'
        self.source.write_bytes(b'database dump')
        self.cert = self.stage / 'qa_passed.json'
        self.cert.write_text(json.dumps({'database': self.database, 'commit': 'a' * 40}))
        self.row = {'database': self.database, 'retained_source': {
            'path': str(self.source), 'bytes': self.source.stat().st_size,
            'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()}}
        self.proof = {'root_capture_ns': int((datetime.now(timezone.utc).timestamp() + 60) * 1e9)}

    def candidate(self, existing=(), references=()):
        return cleanup.candidate(self.row, set(existing), references, self.proof)

    def test_safe_candidate_does_not_change_preserved_files(self):
        result = self.candidate()
        self.assertEqual(result['path'], str(self.path))
        self.assertEqual(result['tree']['bytes'], 10)
        self.assertEqual(self.source.read_bytes(), b'database dump')
        self.assertTrue(self.cert.is_file())

    def test_live_database_and_runtime_parent_reference_rejected(self):
        for existing, references in [([self.database], []), ([], [str(self.stage / 'data')])]:
            with self.subTest(existing=existing, references=references), self.assertRaises(ValueError):
                self.candidate(existing, references)

    def test_dump_and_certificate_mismatch_rejected(self):
        self.source.write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError, 'source dump changed'):
            self.candidate()
        self.source.write_bytes(b'database dump')
        self.cert.write_text(json.dumps({'database': 'OTHER', 'commit': 'a' * 40}))
        with self.assertRaisesRegex(ValueError, 'certificate'):
            self.candidate()

    def test_path_escape_and_mount_rejected(self):
        self.row['retained_source']['path'] = str(self.root.parent / 'source.dump')
        with self.assertRaisesRegex(ValueError, 'allowed root'):
            self.candidate()
        self.row['retained_source']['path'] = str(self.source)
        with patch.object(cleanup, 'mount_paths', return_value=[self.path / 'ab']):
            with self.assertRaisesRegex(ValueError, 'mount inside'):
                self.candidate()

    def test_newer_files_rejected_and_inventory_changes(self):
        original = self.candidate()['tree']
        (self.path / 'ab/attachment').write_bytes(b'changed')
        self.assertNotEqual(original, self.candidate()['tree'])
        self.proof['root_capture_ns'] = 1
        with self.assertRaisesRegex(ValueError, 'newer than'):
            self.candidate()

    def test_symlinks_rejected(self):
        link = self.path / 'ab/link'
        try:
            link.symlink_to(self.source)
        except OSError:
            self.skipTest('symlink privilege unavailable on this host')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.candidate()

    def test_snapshot_proof_requires_both_current_ready_disks(self):
        now = datetime.now(timezone.utc)
        path = self.root / 'snapshot-proof.json'
        rows = [{'name': disk, 'id': str(index + 1), 'status': 'READY',
                 'sourceDisk': cleanup.DISK_PREFIX + disk, 'creationTimestamp': now.isoformat()}
                for index, disk in enumerate(cleanup.DISKS)]
        path.write_text(json.dumps(rows), encoding='utf-8-sig')
        self.assertIn('root_capture_ns', cleanup.snapshots(path, now))
        rows[0]['status'] = 'UPLOADING'
        path.write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError, 'READY'):
            cleanup.snapshots(path, now)

    def test_apply_changed_inventory_stops_before_delete(self):
        planned = self.candidate()
        output = self.root / 'plan.json'
        output.write_text(json.dumps({'schema': 1, 'history_sha256': cleanup.HISTORY_SHA,
                          'snapshot_proof': self.proof, 'candidates': [planned]}))
        (self.path / 'ab/attachment').write_bytes(b'changed after plan')
        with (patch.object(cleanup, 'retired', return_value={self.database: self.row}),
              patch.object(cleanup, 'snapshots', return_value=self.proof),
              patch.object(cleanup, 'databases', return_value=set()),
              patch.object(cleanup.managed, 'runtime_references', return_value=[]),
              patch.object(cleanup, 'free_bytes', return_value=123),
              patch.object(cleanup, 'atomic', side_effect=lambda p, v: p.write_text(json.dumps(v))),
              patch.object(cleanup.managed, 'remove_path') as remove):
            with self.assertRaisesRegex(ValueError, 'candidate changed'):
                cleanup.apply(output, self.root / 'snapshot-proof.json')
            remove.assert_not_called()
        self.assertTrue(self.path.is_dir())

    def test_apply_rechecks_database_and_references_after_tree_scan(self):
        for index, (database_states, references) in enumerate([
                ([set(), {self.database}], [[], []]),
                ([set(), set()], [[], [str(self.stage / 'data')]])]):
            with self.subTest(index=index):
                output = self.root / ('race' + str(index) + '.json')
                output.write_text(json.dumps({'schema': 1,
                    'history_sha256': cleanup.HISTORY_SHA,
                    'snapshot_proof': self.proof, 'candidates': [self.candidate()]}))
                with (patch.object(cleanup, 'retired', return_value={self.database: self.row}),
                      patch.object(cleanup, 'snapshots', return_value=self.proof),
                      patch.object(cleanup, 'databases', side_effect=database_states),
                      patch.object(cleanup.managed, 'runtime_references', side_effect=references),
                      patch.object(cleanup, 'free_bytes', return_value=123),
                      patch.object(cleanup, 'atomic', side_effect=lambda p, v: p.write_text(json.dumps(v))),
                      patch.object(cleanup.managed, 'remove_path') as remove):
                    with self.assertRaisesRegex(ValueError, 'appeared before removal'):
                        cleanup.apply(output, self.root / 'snapshot-proof.json')
                    remove.assert_not_called()
                self.assertTrue(self.path.is_dir())


if __name__ == '__main__':
    unittest.main()
