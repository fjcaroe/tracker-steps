"""Rasterize the existing Steps SVG path with Pillow, without inventing a new logo.
Run from any directory. Apple applies its own icon mask; output has square corners.
"""
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
svg = (ROOT / 'mobile/public/icon.svg').read_text()
path = re.search(r'<path d="([^"]+)"', svg).group(1)
points = []
x = y = 0.0
control = (0.0, 0.0)
for token, arguments in re.findall(r'([Mclsz])([^Mclsz]*)', path):
    numbers = [float(n) for n in re.findall(r'-?\d+(?:\.\d+)?', arguments)]
    if token == 'M':
        x, y = numbers
        points.append((x, y))
    elif token == 'l':
        for i in range(0, len(numbers), 2):
            x, y = x + numbers[i], y + numbers[i + 1]
            points.append((x, y))
        control = (x, y)
    elif token in ('c', 's'):
        count = 6 if token == 'c' else 4
        for i in range(0, len(numbers), count):
            if token == 'c':
                a, b, c, d, e, f = numbers[i:i + count]
            else:
                a, b = x - control[0], y - control[1]
                c, d, e, f = numbers[i:i + count]
            for step in range(1, 41):
                t = step / 40
                u = 1 - t
                points.append((u ** 3 * x + 3 * u ** 2 * t * (x + a) + 3 * u * t ** 2 * (x + c) + t ** 3 * (x + e), u ** 3 * y + 3 * u ** 2 * t * (y + b) + 3 * u * t ** 2 * (y + d) + t ** 3 * (y + f)))
            control = (x + c, y + d)
            x, y = x + e, y + f
    elif token != 'z':
        raise ValueError(f'Unexpected token {token}')

icon = Image.new('RGB', (2048, 2048), '#123c33')
ImageDraw.Draw(icon).polygon([(x * 4, y * 4) for x, y in points], fill='#d8ff62')
icon = icon.resize((1024, 1024), Image.Resampling.LANCZOS)
for folder, platform in [('App', 'ios'), ('StepsWatch', 'watchos')]:
    target = ROOT / f'mobile/ios/App/{folder}/Assets.xcassets/AppIcon.appiconset'
    target.mkdir(parents=True, exist_ok=True)
    icon.save(target / 'Steps-1024.png')
    (target / 'Contents.json').write_text(json.dumps({'images': [{'filename': 'Steps-1024.png', 'idiom': 'universal', 'platform': platform, 'size': '1024x1024'}], 'info': {'author': 'xcode', 'version': 1}}, indent=2) + '\n')
