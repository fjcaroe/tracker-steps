"""Build the integrated agricultural addons without credentials or user data."""
import argparse
import ast
import hashlib
from pathlib import Path
import tarfile
import xml.etree.ElementTree as ET

MODULES = ('step_export', 'step_producers', 'step_producer_fruit_flow',
           'step_inventory_packing', 'step_packing_operations')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
assert not args.output.resolve().is_relative_to(root), 'Use an artifact directory outside the checkout'
allowed = {'.py', '.xml', '.csv', '.js', '.scss', '.css', '.svg', '.png', '.jpg', '.webmanifest', '.md'}
files = [path for name in MODULES for path in (root / name).rglob('*')
         if path.is_file() and path.suffix in allowed and '__pycache__' not in path.parts]
for path in files:
    if path.suffix == '.py':
        ast.parse(path.read_text(encoding='utf-8'), str(path))
    elif path.suffix in {'.xml', '.svg'}:
        ET.parse(path)
args.output.parent.mkdir(parents=True, exist_ok=True)
with tarfile.open(args.output, 'w:gz') as archive:
    for path in sorted(files):
        archive.add(path, arcname=path.relative_to(root), recursive=False)
print('SHA256=' + hashlib.sha256(args.output.read_bytes()).hexdigest())
print('FILES=' + str(len(files)))
