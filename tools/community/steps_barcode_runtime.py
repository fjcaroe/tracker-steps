"""Preserve and verify the source installation used to render the historical Chilean PDF417 invoice stamp."""
import argparse
import base64
from importlib import metadata
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


BARCODE_SHA = "ceb11a9bff6749120f0159f48be4bc67ac4d3d9be549291e6f7bbfcdede0e588"


def wheel(name, version):
    dist = metadata.distribution(name)
    check(dist.version == version, "unqualified-" + name + "-version")
    files = {}
    for item in dist.files:
        key = str(item)
        if "__pycache__" in item.parts or item.suffix in (".pyc", ".pyo"):
            continue
        if name == "Pillow" and item.parts[0] not in ("PIL", "Pillow.libs"):
            continue
        path = Path(dist.locate_file(item))
        body = path.read_bytes()
        if item.hash:
            encoded = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip("=")
            check(item.hash.mode == "sha256" and encoded == item.hash.value and len(body) == item.size, "wheel-RECORD-drift")
        else:
            check(item.name == "RECORD" and key.startswith("pdf417gen-0.7.1.dist-info/"), "unknown-unhashed-wheel-file")
        if key == "../../../bin/pdf417gen":
            key = "bin/pdf417gen"
        else:
            check(not item.is_absolute() and ".." not in item.parts, "unsafe-wheel-file")
            key = "python/" + key
        check(key not in files, "duplicate-wheel-path")
        files[key] = body if name != "Pillow" else sha(body)
    return files


def barcode_facts():
    from pdf417gen import encode, render_image
    import PIL
    check(metadata.version("future") == "0.18.2" and metadata.version("pdf417gen") == "0.7.1" and
          PIL.__version__ == "9.0.1", "wrong-barcode-dependency-version")
    # Follow the invoice renderer with a synthetic Latin-1 string and no original stamps.
    codes = encode("Prueba de impresión fiscal de Steps 0123456789".encode("latin-1"), columns=13, security_level=5)
    image = render_image(codes, scale=1, ratio=3, padding=15)
    pillow = wheel("Pillow", "9.0.1")
    with io.BytesIO() as output:
        image.save(output, format="PNG")
        return {"pillow_members_sha256": sha(canonical(pillow)),
                "pillow_files": len(pillow), "codes_sha256": sha(canonical(codes)),
                "pixel_size": list(image.size), "rgb_sha256": sha(image.convert("RGB").tobytes()),
                "png_sha256": sha(output.getvalue())}


def capture():
    package = metadata.distribution("pdf417gen")
    check(package.metadata["License"] == "MIT" and set(package.requires) == {"Pillow (>=2.0.0)", "future"},
          "unexpected-pdf417-license-or-dependencies")
    files = wheel("pdf417gen", "0.7.1")
    check(len(files) == 22 and "python/pdf417gen-0.7.1.dist-info/LICENSE" in files, "incomplete-pdf417-wheel")
    version = subprocess.check_output(["dpkg-query", "-W", "-f=${Version}", "python3-future"]).decode()
    check(version == "0.18.2-2ubuntu0.1", "unknown-source-future")
    md5 = Path("/var/lib/dpkg/info/python3-future.md5sums").read_bytes()
    files["debian/python3-future.md5sums"] = md5
    items = md5.decode().splitlines()
    for line in items:
        expected, relative = line.split(None, 1)
        path = Path("/") / relative
        check(path.resolve(strict=True) == path and not Path(relative).is_absolute(), "unqualified-Debian-payload")
        body = path.read_bytes()
        check(hashlib.md5(body).hexdigest() == expected, "installed-Debian-package-checksum-drift")
        if relative.startswith("usr/lib/python3/dist-packages/"):
            key = "python/" + relative.removeprefix("usr/lib/python3/dist-packages/")
        elif relative.startswith("usr/share/doc/python3-future/") or relative.startswith("usr/bin/python3-"):
            key = "debian/" + relative
        else:
            raise ValueError("unknown-Debian-source-member")
        check(key not in files, "overlapping-Python-providers")
        files[key] = body
    check(len(items) == 218 and "debian/usr/share/doc/python3-future/copyright" in files, "future-license-not-preserved")
    proof = {"versions": {"pdf417gen": "0.7.1", "future": "0.18.2", "Pillow": "9.0.1"},
             "debian_future_version": version, "source_pdf417_files": 22, "source_future_files": len(items),
             "members": {k: [len(v), sha(v)] for k, v in files.items()}, "reference": barcode_facts()}
    files["runtime.json"] = canonical(proof)
    with io.BytesIO() as result:
        with tarfile.open(fileobj=result, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, data in sorted(files.items()):
                entry = tarfile.TarInfo(name)
                entry.size, entry.mode = len(data), 0o644
                archive.addfile(entry, io.BytesIO(data))
        return gzip.compress(result.getvalue(), mtime=0)


def verify(archive, expected_sha, destination=None):
    check(sha(archive.read_bytes()) == expected_sha, "barcode-runtime-archive-digest")
    with tarfile.open(archive) as data:
        index = json.load(data.extractfile("runtime.json"))
        members = index["members"]
        check(len(members) == 241 and index["versions"] == {"pdf417gen": "0.7.1", "future": "0.18.2", "Pillow": "9.0.1"}
              and index["reference"]["pillow_files"] == 113, "barcode-runtime-coverage")
        pending = set(members) | {"runtime.json"}
        for item in data:
            name = item.name
            key = PurePosixPath(name)
            check(name in pending and item.isfile() and not key.is_absolute() and ".." not in key.parts,
                  "unrecognized-barcode-package-member")
            pending.remove(name)
            if name == "runtime.json":
                continue
            body = data.extractfile(item).read()
            check([len(body), sha(body)] == members[name], "barcode-package-file-drift")
            if destination:
                target = destination / name
                check(target.resolve() == target and target.is_relative_to(destination), "invalid-barcode-target")
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    with target.open("xb") as out:
                        out.write(body)
                    target.chmod(0o644)
                check(target.read_bytes() == body, "changed-local-barcode-file")
        check(not pending, "missing-barcode-payload")
    if destination:
        check({p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()} == members.keys(),
              "additional-barcode-runtime-files")
    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["capture", "probe", "verify"])
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--extract", type=Path)
    args = parser.parse_args()
    if args.phase == "capture":
        sys.stdout.buffer.write(capture())
    elif args.phase == "probe":
        print(json.dumps(barcode_facts(), sort_keys=True))
    else:
        summary = verify(args.archive, args.sha256, args.extract)
        print(json.dumps({k: v for k, v in summary.items() if k != "members"}, indent=2))
