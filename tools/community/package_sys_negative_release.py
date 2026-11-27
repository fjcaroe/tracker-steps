"""Assemble the SyS negative-net update with its complete, independently usable .6.2 base."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


BASE_INDEX = "9631b6cf47ac43a798622da746bdd044e8921cbaed356f753af161cc81ea7cfe"
RECEIPTS = ("native-direct-activity.json", "native-verified-activity.json", "negative.json",
            "negative-computed.json", "regression.json", "protection.json")
UPDATE_TOOLS = ("prepare_sys_negative_net.py", "load_steps_sales_extension.py", "run_focal_print_command.py",
                "package_sys_negative_release.py")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def link_checked(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        os.link(source, target)
    if not target.samefile(source) and sha(target) != sha(source):
        raise ValueError(f"Different existing release file {target.name}")


def assemble(base, results, destination):
    from prepare_sys_negative_net import RELEASE

    if sha(base / "release.json") != BASE_INDEX:
        raise ValueError("The .6.2 recovery release differs")
    for source in base.rglob("*"):
        if source.is_file():
            link_checked(source, destination / "base" / source.relative_to(base))
    archive = "negative-net-" + RELEASE + ".tar"
    if sha(results / archive) != RELEASE:
        raise ValueError("The negative-net provider differs")
    for name in (archive, *RECEIPTS):
        link_checked(results / name, destination / "update" / name)
    sources = {path.name: path for path in (base / "tools").glob("*.py")}
    for name in UPDATE_TOOLS:
        sources[name] = Path(__file__).with_name(name)
    for name, source in sources.items():
        target = destination / "tools" / name
        target.parent.mkdir(exist_ok=True)
        data = source.read_bytes().replace(b"\r\n", b"\n")
        if target.exists() and target.read_bytes() != data:
            raise ValueError("Different existing release helper " + name)
        target.write_bytes(data)
    index = destination / "release.json"
    members = {p.relative_to(destination).as_posix(): [p.stat().st_size, sha(p)] for p in destination.rglob("*")
               if p.is_file() and p != index}
    release = {"base_index": BASE_INDEX, "modules": 193, "version": "18.0.1.6.3", "provider": archive, "files": members}
    body = json.dumps(release, sort_keys=True, separators=(",", ":")).encode()
    if index.exists() and index.read_bytes() != body:
        raise ValueError("Different existing final release")
    index.write_bytes(body)
    verify(destination)


def verify(destination):
    from prepare_sys_negative_net import RELEASE
    from package_sys_operator_release import verify as verify_base

    manifest = destination / "release.json"
    release = json.loads(manifest.read_bytes())
    if release["base_index"] != BASE_INDEX or sha(destination / "base/release.json") != BASE_INDEX:
        raise ValueError("The embedded .6.2 base release differs")
    if release["provider"] != "negative-net-" + RELEASE + ".tar" or sha(destination / "update" / release["provider"]) != RELEASE:
        raise ValueError("The .6.3 provider differs")
    actual = {p.relative_to(destination).as_posix(): [p.stat().st_size, sha(p)] for p in destination.rglob("*")
              if p.is_file() and p != manifest}
    if actual != release["files"]:
        raise ValueError("Restore inputs differ from the release")
    verify_base(destination / "base")
    print(f"Verified {len(actual)} components with SHA-256 {sha(manifest)}")


def restore(destination):
    verify(destination)
    if os.name != "posix" or os.getuid() != 0 or not os.path.ismount("/dev/shm"):
        raise ValueError("The private WSL QA userspace is required")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", SYS_NET_FINAL="1")
    base = destination / "base"
    subprocess.run([sys.executable, str(base / "tools/package_sys_operator_release.py"), "restore", str(base)], check=True, env=env)
    runner = destination / "tools/prepare_sys_negative_net.py"
    subprocess.run([sys.executable, str(runner), "clone"], check=True, env=env)
    release = json.loads((destination / "release.json").read_bytes())
    subprocess.run([sys.executable, str(runner), "upgrade", "--package", str(destination / "update" / release["provider"])],
                   check=True, env=env)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("assemble", "verify", "restore"))
    parser.add_argument("destination", type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--results", type=Path)
    args = parser.parse_args()
    if args.stage == "assemble":
        if not args.base or not args.results:
            parser.error("assemble needs --base and --results")
        assemble(args.base.resolve(), args.results.resolve(), args.destination.resolve())
    else:
        {"verify": verify, "restore": restore}[args.stage](args.destination.resolve())
