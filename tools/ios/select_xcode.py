"""Choose an installed stable Xcode 26, never silently fall back to an obsolete SDK."""
import os
import plistlib
import re
from pathlib import Path

available = []
for app in Path('/Applications').glob('Xcode*.app'):
    if re.search(r'beta|release.candidate|\bRC\b', app.name, re.I):
        continue
    try:
        version = plistlib.loads((app / 'Contents/version.plist').read_bytes())['CFBundleShortVersionString']
        parsed = tuple(int(n) for n in version.split('.'))
    except (OSError, ValueError, KeyError):
        continue
    if parsed[0] == 26:
        available.append((parsed, app))
if not available:
    raise SystemExit('A stable Xcode 26 installation is required for the Apple beta build.')
version, selected = max(available, key=lambda item: item[0])
developer_dir = selected / 'Contents/Developer'
with open(os.environ['GITHUB_ENV'], 'a') as output:
    output.write(f'DEVELOPER_DIR={developer_dir}\n')
print(f'Selected stable Xcode {".".join(map(str, version))}.')
