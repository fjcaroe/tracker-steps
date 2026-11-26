"""Archive validation tests; no SSH connection or remote deletion is performed."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import download_verified_backup_archive as client


class ArchiveValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'input.tar.gz'
        self.data = b'old backup contents\x00\xff'
        self.directory = {'path': 'opt/backups/fixture', 'type': 'directory',
                          'size': 0, 'mode': 0o750, 'uid': 42, 'gid': 43,
                          'mtime_ns': 1700000000123456789}
        self.file = dict(self.directory, path='opt/backups/fixture/database.dump',
                         type='file', size=len(self.data), mode=0o640,
                         sha256=hashlib.sha256(self.data).hexdigest())
        self.plan = {'schema': 1, 'sources': [{'path': '/opt/backups/fixture',
                     'entries': [self.directory, self.file]}],
                     'logical_bytes': len(self.data), 'entry_count': 2}

    def build(self, entries=None, contents=None, symlink=False):
        entries = entries if entries is not None else [self.directory, self.file]
        with tarfile.open(self.path, 'w:gz', format=tarfile.PAX_FORMAT) as archive:
            for entry in entries:
                member = tarfile.TarInfo(entry['path'])
                member.mode, member.uid, member.gid = entry['mode'], entry['uid'], entry['gid']
                member.pax_headers['mtime'] = str(client.Decimal(entry['mtime_ns']) / 1_000_000_000)
                if entry['type'] == 'directory':
                    member.type = tarfile.DIRTYPE
                    archive.addfile(member)
                elif symlink:
                    member.type, member.linkname = tarfile.SYMTYPE, '/outside/valuable-data'
                    archive.addfile(member)
                else:
                    data = self.data if contents is None else contents
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
        return self.path.read_bytes()

    def test_full_valid_archive_is_read_without_extraction(self):
        self.build()
        self.assertEqual(client.verify_archive(self.path, self.plan),
                         {'files': 1, 'entries': 2, 'logical_bytes': len(self.data)})
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_changed_payload_is_rejected(self):
        self.build(contents=b'X' * len(self.data))
        with self.assertRaisesRegex(ValueError, 'content mismatch'):
            client.verify_archive(self.path, self.plan)

    def test_extra_and_duplicate_archive_members_are_rejected(self):
        for extra in [dict(self.file, path='opt/backups/fixture/unplanned.dump'), self.file]:
            with self.subTest(extra=extra['path']):
                self.build([self.directory, self.file, extra])
                with self.assertRaisesRegex(ValueError, 'extra or duplicate'):
                    client.verify_archive(self.path, self.plan)

    def test_missing_member_is_rejected(self):
        self.build([self.directory])
        with self.assertRaisesRegex(ValueError, 'missing tar members'):
            client.verify_archive(self.path, self.plan)

    def test_symlink_payload_cannot_substitute_for_regular_file(self):
        self.build(symlink=True)
        with self.assertRaisesRegex(ValueError, 'type mismatch'):
            client.verify_archive(self.path, self.plan)

    def test_ownership_mode_and_mtime_mismatches_are_rejected(self):
        for field, value in [('uid', 99), ('mode', 0o777), ('mtime_ns', 1700000000000000000)]:
            with self.subTest(field=field):
                self.build([self.directory, dict(self.file, **{field: value})])
                with self.assertRaises(ValueError):
                    client.verify_archive(self.path, self.plan)

    def test_truncated_gzip_trailer_is_read_and_rejected(self):
        self.build()
        self.path.write_bytes(self.path.read_bytes()[:-3])
        with self.assertRaises((EOFError, OSError, ValueError)):
            client.verify_archive(self.path, self.plan)

    def test_plan_path_escape_is_rejected(self):
        self.file['path'] = 'opt/backups/fixture/../../outside'
        with self.assertRaisesRegex(ValueError, 'noncanonical'):
            client.expected_members(self.plan)

    def test_plan_source_root_is_restricted(self):
        self.plan['sources'][0]['path'] = '/var/lib/postgresql'
        with self.assertRaisesRegex(ValueError, 'source root'):
            client.expected_members(self.plan)

    def test_stream_receipt_binds_plan_payload_size_and_clean_exit(self):
        receipt = {'complete': True, 'tar_exit': 0, 'gzip_exit': 0,
                   'plan_sha256': 'a', 'archive_sha256': 'b', 'archive_bytes': 123}
        client.validate_stream_receipt(receipt, 'a', 'b', 123)
        for field, value in [('complete', False), ('tar_exit', 1), ('gzip_exit', 1),
                             ('plan_sha256', 'other'), ('archive_sha256', 'other'),
                             ('archive_bytes', 124)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                client.validate_stream_receipt(dict(receipt, **{field: value}), 'a', 'b', 123)

    def test_local_disk_reserve_is_checked_before_starting_stream(self):
        with (patch.object(client, 'remote_read', return_value=json.dumps(self.plan).encode()),
              patch.object(client.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=1)),
              patch.object(client.subprocess, 'Popen') as popen):
            with self.assertRaisesRegex(ValueError, 'insufficient local space'):
                client.download('odoo-new', '/tool.py', '/plan.json',
                                self.root / 'output.tar.gz', 10, 1024 ** 3)
            popen.assert_not_called()

    def test_valid_stream_hash_alone_never_authorizes_removal(self):
        payload = self.build(contents=b'X' * len(self.data))
        raw_plan = json.dumps(self.plan).encode()
        remote = {'complete': True, 'tar_exit': 0, 'gzip_exit': 0,
                  'plan_sha256': hashlib.sha256(raw_plan).hexdigest(),
                  'archive_sha256': hashlib.sha256(payload).hexdigest(),
                  'archive_bytes': len(payload)}
        process = Mock(stdout=io.BytesIO(payload))
        process.wait.return_value = process.poll.return_value = 0
        output = self.root / 'output.tar.gz'
        with (patch.object(client, 'remote_read', side_effect=[raw_plan, json.dumps(remote).encode()]),
              patch.object(client.subprocess, 'Popen', return_value=process),
              patch.object(client.subprocess, 'run') as run):
            with self.assertRaisesRegex(ValueError, 'content mismatch'):
                client.download('odoo-new', '/tool.py', '/plan.json', output, 0, 1024 ** 3, True)
            run.assert_not_called()
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name + '.part').exists())

    def test_pinned_noninteractive_ssh_and_alias_validation(self):
        command = client.ssh_command('odoo-new', ['sudo', '-n', 'cat', '/a path'])
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertIn('BatchMode=yes', command)
        self.assertIn("'/a path'", command[-1])
        with self.assertRaises(ValueError):
            client.ssh_command('-oProxyCommand=anything', ['true'])


if __name__ == '__main__':
    unittest.main()
