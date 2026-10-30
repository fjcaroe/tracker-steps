"""Trust-boundary regressions, with no private data or database access."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import original_external_references_defaults_replay as replay


class TrustedReplayCase(unittest.TestCase):
    def inventory(self):
        files = {name: b'opaque-evidence' for name in replay.file_inventory()}
        manifest = {'schema': 1, 'git_commit': replay.REVISION,
            'database_writes': False, 'writer_authorized': False,
            'global_guard_counts_unchanged': True, 'anchored_policy_live_handover_evaluated': False,
            'files': {name: replay.sha(raw) for name, raw in files.items()}}
        files['export-manifest.json'] = json.dumps(manifest).encode()
        return files, manifest

    def test_manifest_requires_all19_and_rejects_missing_extra_or_changed_files(self):
        files, manifest = self.inventory()
        replay.validate_inventory(files, manifest)
        for change in ('extra', 'missing', 'bytes', 'authority'):
            changed, altered = deepcopy(files), deepcopy(manifest)
            if change == 'extra': changed['unsealed.py'] = b'raise AssertionError()'
            elif change == 'missing': changed.pop(next(iter(replay.file_inventory())))
            elif change == 'bytes': changed[next(iter(replay.file_inventory()))] += b'changed'
            else: altered['writer_authorized'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                replay.validate_inventory(changed, altered)

    def test_archive_symlinks_and_path_traversal_are_not_extracted(self):
        with tempfile.TemporaryDirectory() as folder:
            for kind in ('symlink', 'traversal', 'duplicate'):
                archive = Path(folder, kind + '.tar.gz')
                with tarfile.open(archive, 'w:gz') as stream:
                    info = tarfile.TarInfo('../outside.py' if kind == 'traversal' else 'source.py')
                    if kind == 'symlink':
                        info.type, info.linkname = tarfile.SYMTYPE, '/etc/passwd'
                        stream.addfile(info)
                    else:
                        info.size = 4
                        stream.addfile(info, io.BytesIO(b'pass'))
                        if kind == 'duplicate': stream.addfile(info, io.BytesIO(b'pass'))
                with patch.object(replay, 'ARCHIVE_SHA256', replay.sha(archive.read_bytes())):
                    with self.subTest(kind=kind), self.assertRaises(ValueError):
                        replay.read_archive(archive)
            self.assertFalse(Path(folder, 'outside.py').exists())

    def test_artifact_python_must_match_git_before_any_import(self):
        files, manifest = self.inventory()
        for name in replay.SOURCES:
            files['typed-defaults/source/' + name] = b'raise AssertionError("archive-code-executed")'
        with patch.object(replay, 'read_archive', return_value=(files, manifest)), \
                patch.object(replay.subprocess, 'check_output', return_value=b'# trusted Git bytes\n'), \
                patch.object(replay.importlib, 'import_module') as imported:
            with self.assertRaisesRegex(ValueError, 'not-exact-trusted-git-source'):
                replay.replay('unused.tar.gz', '.')
            imported.assert_not_called()


if __name__ == '__main__':
    unittest.main()
