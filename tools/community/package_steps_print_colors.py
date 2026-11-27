"""Rebuild the exact print extension used to compare the original Steps sales documents."""
import argparse
from hashlib import sha256
import io
from pathlib import Path
import tarfile


MODULE = 'step_report_print_colors'
FILES = ('__init__.py', '__manifest__.py', 'static/src/scss/print_colors.scss')
EXPECTED_SHA256 = 'db1f4c20809563d81e759b2d03c76b1ed57f547d02e4b320eca7901f4cc19dc9'


def build(root):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for name in FILES:
            member = Path(MODULE)/name
            contents = (root/member).read_bytes().replace(b'\r\n', b'\n')
            entry = tarfile.TarInfo(member.as_posix())
            entry.mode, entry.size = 0o644, len(contents)
            archive.addfile(entry, io.BytesIO(contents))
    data = stream.getvalue()
    if sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError('The print extension differs from the verified release.')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    payload = build(Path(__file__).resolve().parents[2])
    if args.output is not None:
        with args.output.open('xb') as output:
            output.write(payload)
    print(EXPECTED_SHA256)
