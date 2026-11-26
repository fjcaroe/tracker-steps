"""Filesystem safety tests; no SSH, sudo, database, or Linux lock is used."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location('cleanup_inactive_temp',
    Path(__file__).with_name('cleanup_inactive_temp.py'))
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


class CleanupSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'steps-fixture'
        self.project.mkdir()
        (self.project / 'package-lock.json').write_text('{}')
        self.target = self.project / 'node_modules'
        self.target.mkdir()
        (self.target / 'dependency.js').write_text('module.exports = 1;')
        self.old = time.time() - 9 * 24 * 3600
        self.cutoff = time.time() - cleanup.MIN_AGE_SECONDS
        self.age(self.project)

    def tearDown(self):
        self.temp.cleanup()

    def age(self, root):
        for current, directories, files in os.walk(root, topdown=False, followlinks=False):
            for name in files + directories:
                os.utime(Path(current) / name, (self.old, self.old))
            os.utime(current, (self.old, self.old))

    def inspect(self, target=None, references=(), mounts=()):
        return cleanup.inspect(target or self.target, self.cutoff,
            references, mounts, self.root)

    def apply(self, plan, references=()):
        receipt = self.root / 'result.json'

        def remove(path, root):
            self.assertEqual(root, self.root)
            self.assertTrue(path.resolve().is_relative_to(root))
            shutil.rmtree(path)

        return cleanup.apply_plan(plan, receipt, self.root,
            collect=lambda: references, mounts=lambda: [], remove=remove)

    def plan(self):
        return cleanup.make_plan([self.target], self.cutoff, [], [], self.root)

    def test_explicit_dependency_cleanup_preserves_sources_and_lockfile(self):
        source = self.project / 'source.py'
        source.write_text('valuable uncommitted source')
        plan = self.plan()
        self.assertEqual(len(plan['candidates']), 1)
        result = self.apply(plan)
        self.assertEqual(len(result['removed']), 1)
        self.assertFalse(self.target.exists())
        self.assertTrue(source.exists())
        self.assertTrue((self.project / 'package-lock.json').exists())

    def test_non_steps_parent_and_unapproved_descendants_are_rejected(self):
        with self.assertRaises(cleanup.UnsafeCandidate):
            self.inspect(self.root)
        with self.assertRaises(cleanup.UnsafeCandidate):
            self.inspect(self.target / 'nested')
        other = self.root / 'another-project'
        other.mkdir()
        with self.assertRaises(cleanup.UnsafeCandidate):
            self.inspect(other)

    def test_missing_dependency_marker_is_rejected(self):
        (self.project / 'package-lock.json').unlink()
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'requirements file missing'):
            self.inspect()

    def test_recent_descendant_is_rejected_even_when_root_is_old(self):
        os.utime(self.target / 'dependency.js', None)
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'newer than seven days'):
            self.inspect()

    def test_project_reference_protects_lazily_loaded_dependencies(self):
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'referenced'):
            self.inspect(references=[str(self.project / 'server.js')])

    def test_nested_mount_is_rejected(self):
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'mount point'):
            self.inspect(mounts=[self.target / 'nested-bind-mount'])

    def test_no_git_or_linked_worktree_is_preserved_as_whole_directory(self):
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'independent Git clone'):
            self.inspect(self.project)
        (self.project / '.git').write_text('gitdir: /some/other/live/repository')
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'independent Git clone'):
            self.inspect(self.project)

    def test_dirty_git_and_unrecognized_ignored_files_are_preserved(self):
        (self.project / '.git').mkdir()
        self.age(self.project)
        for output in (b' M source.py\0', b'?? source.py\0', b'!! .env\0'):
            with self.subTest(output=output), patch.object(cleanup.subprocess, 'run',
                    return_value=subprocess.CompletedProcess([], 0, output, b'')):
                with self.assertRaises(cleanup.UnsafeCandidate):
                    self.inspect(self.project)

    def test_ignored_generated_dependencies_do_not_make_clone_dirty(self):
        (self.project / '.git').mkdir()
        self.age(self.project)
        with patch.object(cleanup.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 0, b'!! node_modules/\0', b''),
                subprocess.CompletedProcess([], 0, b'0\n', b'')]):
            result = self.inspect(self.project)
        self.assertEqual(result['kind'], 'clean_clone')

    def test_whole_clone_with_local_unique_commits_is_preserved_without_fetch(self):
        (self.project / '.git').mkdir()
        self.age(self.project)
        for returncode, output in ((0, b'1\n'), (0, b'3\n'), (128, b'')):
            with self.subTest(output=output), patch.object(cleanup.subprocess, 'run', side_effect=[
                    subprocess.CompletedProcess([], 0, b'', b''),
                    subprocess.CompletedProcess([], returncode, output, b'')]) as run:
                with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'remote refs'):
                    self.inspect(self.project)
                self.assertEqual(run.call_args.kwargs['env']['GIT_NO_LAZY_FETCH'], '1')
                self.assertEqual(run.call_args.kwargs['env']['GIT_ALLOW_PROTOCOL'], '')
                self.assertIn('--remotes', run.call_args.args[0])

    def browser_cache(self):
        browsers = self.project / 'browsers'
        browsers.mkdir()
        (browsers / '.links').mkdir()
        for name in ('chromium-1194', 'chromium_headless_shell-1194', 'ffmpeg-1011'):
            revision = browsers / name
            revision.mkdir()
            (revision / 'binary').write_bytes(b'downloaded browser distribution')
        self.age(browsers)
        return browsers

    def test_known_playwright_cache_can_be_removed_while_sources_survive(self):
        browsers = self.browser_cache()
        source = self.project / 'browser-test.cjs'
        source.write_text('valuable test source')
        plan = cleanup.make_plan([browsers], self.cutoff, [], [], self.root)
        self.assertEqual(plan['candidates'][0]['kind'], 'browser_cache')
        result = self.apply(plan)
        self.assertEqual(len(result['removed']), 1)
        self.assertTrue(source.exists())
        self.assertTrue(self.target.exists())

    def test_browser_cache_with_unknown_source_directory_is_preserved(self):
        browsers = self.browser_cache()
        (browsers / 'src').mkdir()
        self.age(browsers)
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'unrecognized entry'):
            self.inspect(browsers)

    def test_browser_cache_with_top_level_file_is_preserved(self):
        browsers = self.browser_cache()
        (browsers / 'test.cjs').write_text('source')
        self.age(browsers)
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'unrecognized entry'):
            self.inspect(browsers)

    def test_browser_cache_without_lock_or_with_runtime_reference_is_preserved(self):
        browsers = self.browser_cache()
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'referenced'):
            self.inspect(browsers, references=[str(self.project / 'browser-test.cjs')])
        (self.project / 'package-lock.json').unlink()
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'requirements file missing'):
            self.inspect(browsers)

    def test_changed_descendant_identity_is_revalidated_before_deletion(self):
        plan = self.plan()
        (self.target / 'dependency.js').write_text('changed file with restored mtime')
        os.utime(self.target / 'dependency.js', (self.old, self.old))
        result = self.apply(plan)
        self.assertEqual(result['removed'], [])
        self.assertEqual(len(result['skipped']), 1)
        self.assertTrue(self.target.exists())

    def test_runtime_reference_added_after_plan_prevents_deletion(self):
        result = self.apply(self.plan(), references=[str(self.project / 'app.py')])
        self.assertEqual(result['removed'], [])
        self.assertTrue(self.target.exists())

    def test_plan_cannot_supply_a_recent_cutoff(self):
        plan = self.plan()
        plan['cutoff'] = time.time()
        with self.assertRaisesRegex(cleanup.UnsafeCandidate, 'insufficiently old'):
            self.apply(plan)
        self.assertTrue(self.target.exists())

    def test_plan_evidence_path_is_restricted(self):
        evidence = self.root / 'evidence'
        evidence.mkdir()
        allowed = evidence / 'server-disk-cleanup-fixture' / 'plan.json'
        self.assertEqual(cleanup.evidence_path(allowed, evidence), allowed)
        with self.assertRaises(cleanup.UnsafeCandidate):
            cleanup.evidence_path(evidence / 'other' / 'plan.json', evidence)
        with self.assertRaises(cleanup.UnsafeCandidate):
            cleanup.evidence_path(evidence / 'server-disk-cleanup-fixture' / 'plan.sh', evidence)

    def test_symlinks_are_not_followed_and_external_target_is_preserved(self):
        outside = self.root / 'outside.txt'
        outside.write_text('recent external data must survive')
        link = self.target / 'external'
        try:
            link.symlink_to(outside)
            os.utime(link, (self.old, self.old), follow_symlinks=False)
        except (OSError, NotImplementedError):
            self.skipTest('symlink creation/timestamps unavailable on this host')
        os.utime(self.target, (self.old, self.old))
        result = self.apply(self.plan())
        self.assertEqual(len(result['removed']), 1)
        self.assertTrue(outside.exists())


if __name__ == '__main__':
    unittest.main()
