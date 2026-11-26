"""Safety tests with temporary fixtures only; no SSH, sudo or real backup access."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import archive_old_backups as archive


class FakeProcess:
    def __init__(self, data=b'', code=0):
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(data)
        self.returncode = code

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


class ArchiveSafety(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.backups = self.root / 'backups'
        self.backups.mkdir()
        self.source = self.backups / 'old-batch'
        self.source.mkdir()
        (self.source / 'database.dump').write_bytes(b'original dump bytes')
        (self.source / 'subdir').mkdir()
        (self.source / 'subdir/config').write_bytes(b'private fixture configuration')
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()
        self.plan_path = self.evidence / 'batch.json'
        self.cutoff = '2026-11-01T00:00:00Z'
        self.old = archive.cutoff_ns('2026-10-01T00:00:00Z') / 1e9
        self.age()
        self.addCleanup(patch.stopall)
        patch.object(archive, 'ROOTS', (self.backups,)).start()
        patch.object(archive, 'EVIDENCE', self.evidence).start()
        patch.object(archive, 'runtime_references', return_value=[]).start()
        patch.object(archive, 'mount_paths', return_value=[]).start()
        patch.object(archive, 'free_bytes', return_value=12345).start()

    def age(self):
        for node in sorted(self.source.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if not node.is_symlink():
                os.utime(node, (self.old, self.old))
        os.utime(self.source, (self.old, self.old))

    def plan(self):
        value = archive.build_plan([self.source], self.cutoff)
        self.plan_path.write_text(json.dumps(value))
        return value

    def receipt(self):
        value = {'complete': True, 'plan_sha256': archive.digest(self.plan_path),
                 'archive_sha256': 'a' * 64, 'archive_bytes': 999,
                 'tar_exit': 0, 'gzip_exit': 0}
        self.plan_path.with_suffix('.stream.json').write_text(json.dumps(value))
        return {'verified': True, 'plan_sha256': value['plan_sha256'],
                'archive_sha256': value['archive_sha256'], 'archive_bytes': value['archive_bytes']}

    def test_plan_hashes_contents_and_preserves_metadata(self):
        plan = self.plan()
        self.assertEqual(plan['entry_count'], 4)
        self.assertEqual(plan['logical_bytes'], 48)
        entry = next(row for row in plan['sources'][0]['entries'] if row['path'].endswith('database.dump'))
        self.assertEqual(entry['sha256'], hashlib.sha256(b'original dump bytes').hexdigest())
        for name in ('size', 'mode', 'uid', 'gid', 'mtime_ns', 'ctime_ns', 'device', 'inode'):
            self.assertIn(name, entry)

    def test_roots_escapes_duplicates_and_mounts_are_rejected(self):
        for paths in ([self.backups], [self.source / 'subdir'], [self.source, self.source]):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                archive.build_plan(paths, self.cutoff)
        with patch.object(archive, 'mount_paths', return_value=[self.source / 'subdir']):
            with self.assertRaisesRegex(ValueError, 'mount inside'):
                self.plan()

    def test_runtime_nginx_reference_and_recent_file_protect_source(self):
        with patch.object(archive, 'runtime_references', return_value=['alias ' + str(self.source)]):
            with self.assertRaisesRegex(ValueError, 'referenced'):
                self.plan()
        os.utime(self.source / 'database.dump', None)
        with self.assertRaisesRegex(ValueError, 'newer than cutoff'):
            self.plan()

    def test_symlinks_are_rejected(self):
        try:
            (self.source / 'link').symlink_to(self.source / 'database.dump')
        except OSError:
            self.skipTest('symlink privilege unavailable on this host')
        self.age()
        with self.assertRaisesRegex(ValueError, 'symlink or special'):
            self.plan()

    def test_revalidation_detects_changed_content_with_restored_mtime(self):
        plan = self.plan()
        (self.source / 'database.dump').write_bytes(b'changed dump bytes!')
        self.age()
        with self.assertRaisesRegex(ValueError, 'changed since plan'):
            archive.revalidate(plan)

    def test_local_receipt_requires_true_and_all_exact_stream_values(self):
        self.plan()
        receipt = self.receipt()
        for field, value in [('verified', 'true'), ('verified', 1), ('archive_sha256', 'b' * 64),
                             ('archive_bytes', 998), ('archive_bytes', True), ('plan_sha256', 'b' * 64)]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                archive.verified_receipt(self.plan_path, dict(receipt, **{field: value}))

    def test_prune_revalidates_and_preserves_changed_source(self):
        self.plan()
        local = self.evidence / 'local.json'
        local.write_text(json.dumps(self.receipt()))
        (self.source / 'database.dump').write_bytes(b'changed')
        self.age()
        with self.assertRaisesRegex(ValueError, 'changed since plan'):
            archive.prune(self.plan_path, local)
        self.assertTrue(self.source.exists())

    def test_prune_after_verified_copy_removes_only_selected_path(self):
        self.plan()
        local = self.evidence / 'local.json'
        local.write_text(json.dumps(self.receipt()))
        other = self.backups / 'keep-recent'
        other.mkdir()
        with patch.object(archive, 'managed', return_value=types.SimpleNamespace(
                remove_path=lambda path, root: shutil.rmtree(path))):
            archive.prune(self.plan_path, local)
        result = archive.load(self.plan_path.with_suffix('.prune.json'))
        self.assertTrue(result['complete'])
        self.assertFalse(self.source.exists())
        self.assertTrue(other.exists())
        with self.assertRaises(ValueError):
            archive.prune(self.plan_path, local)

    def test_pipeline_failure_cannot_create_complete_receipt(self):
        self.plan()
        with patch.object(archive.subprocess, 'Popen', side_effect=[FakeProcess(code=1), FakeProcess(b'bytes')]):
            with self.assertRaisesRegex(ValueError, 'tar or gzip failed'):
                archive.stream_archive(self.plan_path, io.BytesIO())
        self.assertFalse(self.plan_path.with_suffix('.stream.json').exists())

    def test_broken_stdout_cannot_create_complete_receipt(self):
        self.plan()
        output = types.SimpleNamespace(write=lambda block: (_ for _ in ()).throw(BrokenPipeError()))
        with patch.object(archive.subprocess, 'Popen', side_effect=[FakeProcess(), FakeProcess(b'bytes')]):
            with self.assertRaises(BrokenPipeError):
                archive.stream_archive(self.plan_path, output)
        self.assertFalse(self.plan_path.with_suffix('.stream.json').exists())

    @unittest.skipUnless(os.name == 'posix' and shutil.which('tar') and shutil.which('gzip'),
                         'GNU tar/gzip integration requires Linux')
    def test_real_stream_is_binary_complete_and_has_exact_members(self):
        (self.source / '000-large-first').write_bytes(os.urandom(1024 * 1024))
        # The member list exceeds pipe buffers; the first incompressible member
        # also exceeds output buffers. This exercises concurrent name feeding.
        for index in range(600):
            (self.source / ('extra-' + str(index) + '-' + 'x' * 100)).write_bytes(b'')
        self.age()
        plan = self.plan()
        output = io.BytesIO()
        archive.stream_archive(self.plan_path, output)
        compressed = output.getvalue()
        self.assertEqual(compressed[:2], b'\x1f\x8b')
        remote = archive.load(self.plan_path.with_suffix('.stream.json'))
        self.assertEqual(remote['archive_bytes'], len(compressed))
        self.assertEqual(remote['archive_sha256'], hashlib.sha256(compressed).hexdigest())
        expected = {entry['path']: entry for source in plan['sources'] for entry in source['entries']}
        actual = {}
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as gz:
            with tarfile.open(fileobj=gz, mode='r|') as tar:
                for member in tar:
                    name = member.name.rstrip('/')
                    self.assertNotIn(name, actual)
                    actual[name] = member
                    if member.isfile():
                        self.assertEqual(hashlib.sha256(tar.extractfile(member).read()).hexdigest(),
                                         expected[name]['sha256'])
            while gz.read(1024 * 1024):
                pass
        self.assertEqual(set(expected), set(actual))


if __name__ == '__main__':
    unittest.main()
