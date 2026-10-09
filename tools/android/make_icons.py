"""Use the existing Steps mark for Android launcher assets and Play's icon."""
import re
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[2]
resources = root / 'mobile/android/app/src/main/res'
icon = Image.open(root / 'mobile/ios/App/App/Assets.xcassets/AppIcon.appiconset/Steps-1024.png')
for density, size in [('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144), ('xxxhdpi', 192)]:
    directory = resources / f'mipmap-{density}'
    directory.mkdir(exist_ok=True)
    for name in ('ic_launcher.png', 'ic_launcher_round.png'):
        icon.resize((size, size), Image.Resampling.LANCZOS).save(directory / name)
svg = (root / 'mobile/public/icon.svg').read_text()
path = re.search(r'<path d="([^"]+)"', svg).group(1)
(resources / 'drawable/ic_launcher_foreground.xml').write_text(f'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="108dp" android:height="108dp" android:viewportWidth="512" android:viewportHeight="512">
  <path android:fillColor="#d8ff62" android:pathData="{path}"/>
</vector>
''')
for file in (resources / 'values').glob('*.xml'):
    text = file.read_text()
    if '<color name="ic_launcher_background">' in text:
        file.write_text(re.sub(r'(<color name="ic_launcher_background">)[^<]*(</color>)', r'\1#123c33\2', text))
