"""Restore only T49's unneeded Admin source edits; preserve all database state."""
import argparse
from pathlib import Path
import shutil
import subprocess
from deploy import FIELDS, patch_field

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("backup", type=Path)
args = parser.parse_args()
backup = args.backup.resolve()
assert backup.parent == Path("/opt/steps_backups") and backup.name.startswith("t49_admin_")
assert not (backup / "deployed-sha256.json").exists(), "Completed deployment cannot use this recovery"
pairs = []
for relative, field in FIELDS.items():
    if not relative.startswith("step_hr/"):
        continue
    target = Path("/opt/fernando_odoo18/custom_addons") / relative
    original = backup / "code" / target.relative_to("/")
    expected = patch_field(original.read_text(), field)
    assert target.read_text() in (original.read_text(), expected), f"Concurrent change: {target}"
    pairs.append((original, target))
subprocess.run(["systemctl", "stop", "odoo18-admin"], check=True)
try:
    for original, target in pairs:
        shutil.copy2(original, target)
        assert target.read_bytes() == original.read_bytes()
finally:
    subprocess.run(["systemctl", "start", "odoo18-admin"], check=True)
subprocess.run(["systemctl", "is-active", "--quiet", "odoo18-admin"], check=True)
print("T49_ADMIN_RESTORED no database changes committed")
