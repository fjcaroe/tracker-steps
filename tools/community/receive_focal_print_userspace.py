"""Install verified public QA runtime files into the shared local WSL chroot, never into the host OS."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tarfile

ROOT = Path("/var/tmp/steps-community-qa-focal")


def member_path(key):
    name = PurePosixPath(key)
    if name.is_absolute() or ".." in name.parts or str(name) != key:
        raise ValueError("Invalid archive path")
    path = ROOT.joinpath(*name.parts)
    if not path.parent.resolve().is_relative_to(ROOT):
        raise ValueError("Archive escapes the local runtime")
    return path


def receive(stage):
    if os.getuid() or ROOT.is_symlink() or ROOT.resolve() != ROOT:
        raise ValueError("Requires the dedicated WSL root directory")
    ROOT.mkdir(mode=0o755, exist_ok=True)
    observed = {}
    manifest = None
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz") as archive:
        for member in archive:
            if not member.isfile() or manifest is not None:
                raise ValueError("Expected only regular files followed by the manifest")
            stream = archive.extractfile(member)
            if member.name == "steps-runtime-manifest.json":
                manifest = json.load(stream)
                continue
            path = member_path(member.name)
            if path.is_symlink() or member.name in observed:
                raise ValueError("Duplicate or indirect regular file")
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = 0o755 if member.mode & 0o111 else 0o644
            temp = path.with_name(path.name + ".steps-partial-" + str(os.getpid()))
            digest = hashlib.sha256()
            try:
                with temp.open("xb") as output:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        output.write(chunk)
                if temp.stat().st_size != member.size:
                    raise ValueError("Truncated archive member")
                if path.exists():
                    with path.open("rb") as current:
                        previous = hashlib.file_digest(current, "sha256").hexdigest()
                    if previous != digest.hexdigest():
                        raise ValueError("Different existing file in runtime: " + member.name)
                else:
                    temp.chmod(mode)
                    os.link(temp, path)
            finally:
                temp.unlink(missing_ok=True)
            observed[member.name] = [member.size, digest.hexdigest(), mode]
    if not manifest or manifest["stage"] != stage or observed != manifest["files"]:
        raise ValueError("The transferred files differ from the source manifest")
    for key, target in sorted(manifest["links"].items(), key=lambda pair: -pair[0].count("/")):
        path = member_path(key)
        dest = (path.parent / target).resolve()
        if Path(target).is_absolute() or not dest.is_relative_to(ROOT):
            raise ValueError("Symlink escapes local runtime")
        if key in ("sbin", "bin", "lib", "lib64"):
            dest.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            raise ValueError("Missing link target: " + key + " -> " + target)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() and os.readlink(path) == target:
            continue
        path.symlink_to(target)
    for folder in ("etc", "proc", "dev", "run", "var/cache/fontconfig", "var/tmp", "work", "tmp"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    (ROOT / "tmp").chmod(0o1777)
    for key, content in {
        "etc/passwd": "root:x:0:0:root:/root:/bin/sh\npostgres:x:61012:61012:QA:/tmp:/bin/sh\nodoo:x:61018:61018:QA:/tmp:/bin/sh\n",
        "etc/group": "root:x:0:\npostgres:x:61012:\nodoo:x:61018:\n",
        "etc/hosts": "127.0.0.1 localhost\n::1 localhost\n",
        "etc/nsswitch.conf": "passwd: files\ngroup: files\nhosts: files\n"
    }.items():
        path = ROOT / key
        if path.exists() and path.read_text() != content:
            raise ValueError("Local account configuration differs")
        if not path.exists():
            path.write_text(content)
    result = ROOT / (stage + "-source-members.json")
    data = json.dumps(manifest, sort_keys=True).encode()
    result.write_bytes(data)
    print(json.dumps({"files": len(observed), "bytes": sum(v[0] for v in observed.values()),
                      "manifest_sha256": hashlib.sha256(data).hexdigest(), "stage": stage}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("pg", "odoo", "extras", "print"))
    receive(parser.parse_args().stage)
