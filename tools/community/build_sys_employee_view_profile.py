"""Build the free HR provider that preserves the original SyS public employee directory."""

import ast
import json
from pathlib import Path
import shutil
import tempfile

from build_sys_upgrade_policy_profile import fingerprint, seal_profile
from custody_sys_previred_filestore import digest
from restore_sys_previred_pair import require


def build_hr_profile(sealed, out):
    source = sealed / "runtime/addons/hr"
    original = source / "models/hr_employee_public.py"
    members = json.loads((sealed / "runtime-members.json").read_bytes())
    original_files = {k.removeprefix("addons/hr/"): v for k, v in members.items() if k.startswith("addons/hr/")}
    require(original_files and {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()} == set(original_files)
            and all((source / k).stat().st_size == v[0] and digest(source / k) == v[1] for k, v in original_files.items()),
            "sealed-HR-module-differs")
    require(digest(original) == "560d99e1919bdca0dd1b4d2ebea30b5d2dcb5357764cc2a8d8f58bcbe1a68afc"
            and ast.literal_eval((source / "__manifest__.py").read_text())["license"] == "LGPL-3", "unreviewed-HR")
    target = out / "employee-profile"
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        profile = Path(tmp) / "addons"
        current = profile / "hr"
        shutil.copytree(source, current)
        code = current / "models/hr_employee_public.py"
        anchor = "    def init(self):\n"
        text = code.read_text()
        require(text.count(anchor) == 1, "unreviewed-HR-view-initializer")
        code.write_text(text.replace(anchor, anchor + "        from .sys_original_employee_view import keep_existing_directory\n"
                                     + "        if keep_existing_directory(self):\n            return\n"))
        helper = current / "models/sys_original_employee_view.py"
        require(not helper.exists(), "unexpected-existing-HR-directory-helper")
        shutil.copyfile(Path(__file__).with_name("sys_original_employee_view.py"), helper)
        for p in (profile, *profile.rglob("*")):
            p.chmod(0o755 if p.is_dir() or p.stat().st_mode & 0o111 else 0o644)
        profile.rename(target)
    files, sha = fingerprint(target)
    expected = {"files": files, "sha256": sha}
    return {**expected, **seal_profile(target, out / "employee-profile.tar", expected),
            "source_files": len(original_files), "original_init_sha256": digest(original)}
