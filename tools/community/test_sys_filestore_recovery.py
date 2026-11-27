import hashlib
from pathlib import Path
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform.startswith('linux'), 'the custody tool uses the Linux shared lock')
class FilestoreRecoveryTest(unittest.TestCase):
    def test_private_bytes_complete_only_missing_primary_objects(self):
        from custody_sys_previred_filestore import capture, restore_objects

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, recovery, output = [root / name for name in ('source', 'recovery', 'output')]
            for folder in (original, recovery, output):
                folder.mkdir()
            catalog = {}
            for content, folder in ((b'present', original), (b'archived', recovery)):
                checksum = hashlib.sha1(content).hexdigest()
                name = checksum[:2] + '/' + checksum
                catalog[name] = len(content)
                path = folder / name
                path.parent.mkdir()
                path.write_bytes(content)
            recovered_name = name
            with self.assertRaisesRegex(ValueError, 'missing-or-invalid'):
                capture(original, output, catalog)
            path.write_bytes(b'incorrect'[:len(content)])
            with self.assertRaisesRegex(ValueError, 'restore-checksum'):
                capture(original, output, catalog, recovery)
            self.assertEqual(list(output.iterdir()), [])
            path.write_bytes(content)
            primary = original / name
            primary.parent.mkdir()
            primary.symlink_to(path)
            with self.assertRaisesRegex(ValueError, 'missing-or-invalid'):
                capture(original, output, catalog, recovery)
            primary.unlink()
            receipt = capture(original, output, catalog, recovery)
            self.assertEqual(receipt['verified_objects'], 2)
            self.assertEqual(receipt['recovered_objects'], [recovered_name])
            restored = root / 'restored'
            restored.mkdir()
            restore_objects(output / 'filestore.tar', restored, catalog)
            self.assertEqual((restored / recovered_name).read_bytes(), content)
