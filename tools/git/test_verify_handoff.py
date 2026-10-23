import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("handoff", Path(__file__).with_name("verify_handoff.py"))
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.repo = self.root / "repo"
        self.run_git(self.root, "init", "--bare", str(self.remote))
        self.run_git(self.root, "clone", str(self.remote), str(self.repo))
        self.run_git(self.repo, "config", "user.email", "test@example.invalid")
        self.run_git(self.repo, "config", "user.name", "Test")
        (self.repo / "source.py").write_text("value = 1\n")
        self.run_git(self.repo, "add", ".")
        self.run_git(self.repo, "commit", "-m", "initial")
        self.run_git(self.repo, "push", "-u", "origin", "HEAD")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def run_git(path, *args):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)

    def test_clean_published(self):
        self.assertEqual(handoff.check(self.repo, True)["problems"], [])

    def test_untracked_and_staged(self):
        (self.repo / "lost.py").write_text("value = 2\n")
        (self.repo / "source.py").write_text("value = 3\n")
        self.run_git(self.repo, "add", "source.py")
        self.assertIn("2 archivo", handoff.check(self.repo)["problems"][0])

    def test_unpublished_commit(self):
        self.run_git(self.repo, "commit", "--allow-empty", "-m", "pending")
        self.assertIn("1 commit(s) sin subir", handoff.check(self.repo, True)["problems"][0])

    def test_ignored_source_cannot_hide_in_temporary_folder(self):
        (self.repo / ".gitignore").write_text("tmp/\n")
        self.run_git(self.repo, "add", ".gitignore")
        self.run_git(self.repo, "commit", "-m", "ignore temporary artifacts")
        (self.repo / "tmp").mkdir()
        (self.repo / "tmp" / "forgotten.py").write_text("value = 1\n")
        vendor = self.repo / "tmp" / "node_modules"
        vendor.mkdir()
        (vendor / "vendor.js").write_text("// dependency\n")
        self.assertIn("1 fuente(s) ignorada(s)", handoff.check(self.repo)["problems"][0])

    def test_missing_upstream_and_detached(self):
        self.run_git(self.repo, "checkout", "-b", "new")
        self.assertIn("rama sin upstream remoto", handoff.check(self.repo, True)["problems"])
        self.run_git(self.repo, "checkout", "--detach")
        self.assertIn("HEAD separado de una rama", handoff.check(self.repo)["problems"])


if __name__ == "__main__":
    unittest.main()
