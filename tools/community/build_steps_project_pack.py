"""Build the verified Steps project overlay using original Community code and the repository providers."""
import argparse
from hashlib import sha256
import io
from pathlib import Path
import tarfile

from steps_project_release import ADDRESS, MODULES, PACKAGE
from verify_converted_backup import check, hash_file


SOURCE_SUFFIXES = {'.py','.xml','.csv','.po','.md','.rst','.txt'}


def build(repo, official, output):
    check(hash_file(official)==ADDRESS,'wrong-official-base-address-extended')
    members = {}
    with tarfile.open(official) as archive:
        for item in archive:
            path = Path(item.name)
            check(item.isfile() and not path.is_absolute() and '..' not in path.parts and
                  path.parts[0]=='base_address_extended' and item.name not in members,'unexpected-address-provider-file')
            members[item.name] = archive.extractfile(item).read()
    for module in MODULES.keys()-{'base_address_extended'}:
        for source in (repo/module).rglob('*'):
            name = source.relative_to(repo)
            if not source.is_file() or set(name.parts)&{'__pycache__','tests','.git'}:
                continue
            data = source.read_bytes()
            members[name.as_posix()] = data.replace(b'\r\n',b'\n') if source.suffix in SOURCE_SUFFIXES else data
    check({name:sum(key.startswith(name+'/') for key in members) for name in MODULES}==MODULES,'project-source-file-count')
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w') as package:
        for name,data in sorted(members.items()):
            member = tarfile.TarInfo(name)
            member.mode,member.size = 0o644,len(data)
            package.addfile(member,io.BytesIO(data))
    body = stream.getvalue()
    check(sha256(body).hexdigest()==PACKAGE,'different-qualified-project-package')
    with output.open('xb') as target:
        target.write(body)
    print(PACKAGE)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo','official','output'):
        parser.add_argument(name,type=Path)
    opts = parser.parse_args()
    build(opts.repo,opts.official,opts.output)
