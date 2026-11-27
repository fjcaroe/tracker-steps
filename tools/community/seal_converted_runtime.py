"""Seal the official Community engine and the effective installed addons into a relocatable private archive."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

from custody_sys_previred_filestore import digest
from restore_sys_previred_pair import require


def resolve_providers(runtime, addons, data, modules):
    code = """
import json, sys
from pathlib import Path
import odoo
from odoo.modules import module
from odoo.tools import config
params = json.load(sys.stdin)
config.parse_config(['--addons-path=' + ','.join(params['addons']), '--data-dir=' + params['data']])
module.initialize_sys_path()
out = {}
for name in params['modules']:
    path = Path(module.get_module_path(name)).resolve(strict=True)
    meta = module.get_manifest(name)
    assert path.is_dir() and meta['license'] != 'OEEL-1'
    out[name] = [str(path), meta['version'], meta['license']]
print('PROVIDERS=' + json.dumps(out))
"""
    cmd = ["unshare", "--net", "sudo", "-n", "-u", "odoo", "env", "PYTHONDONTWRITEBYTECODE=1",
           "PYTHONPATH=" + str(runtime), "/usr/bin/python3.10", "-c", code]
    config = {"addons": list(map(str, addons)), "data": str(data), "modules": sorted(modules)}
    out = subprocess.run(cmd, input=json.dumps(config), text=True, capture_output=True, check=True).stdout
    providers = json.loads(next(line.removeprefix("PROVIDERS=") for line in out.splitlines()
                                if line.startswith("PROVIDERS=")))
    require(providers.keys() == modules.keys(), "effective-provider-set-mismatch")
    return providers


def extract_runtime(archive, target, hashes):
    require(not target.exists() and not target.is_symlink(), "new-runtime-directory-required")
    target.mkdir(mode=0o750)
    with tarfile.open(archive, "r|gz") as bundle:
        pending = set(hashes)
        for member in bundle:
            relative = Path(member.name)
            require(member.isfile() and member.name in pending and not relative.is_absolute()
                    and ".." not in relative.parts, "unknown-or-duplicate-runtime-member")
            pending.remove(member.name)
            size, checksum, mode = hashes[member.name]
            require(member.size == size and member.mode == mode and mode in (0o644,0o755),
                    "runtime-member-properties-differ")
            dest = target / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as incoming, dest.open("xb") as restored:
                shutil.copyfileobj(incoming, restored)
            require(dest.stat().st_size == size and digest(dest) == checksum, "restored-runtime-file-drift")
            dest.chmod(mode)
        require(not pending, "runtime-member-missing")


def seal(runtime, providers, output):
    runtime = runtime.resolve(strict=True)
    # Provider paths come from the official resolver. An overlay can select a licensed
    # module in a managed release via symlink. Authorize only its exact module root.
    allowed = [runtime]
    for name, (origin, version, license_) in providers.items():
        module = Path(origin).resolve(strict=True)
        require(module.name == name and (module / "__manifest__.py").is_file() and license_ != "OEEL-1",
                "unexpected-effective-module-root")
        allowed.append(module)
    hashes = {}
    provenance = {}
    archive = output / "runtime.tar.gz"
    target = output / "runtime"
    skip = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
    with tarfile.open(archive, "x:gz", compresslevel=1) as bundle:
        def add(origin, rel, ancestors=frozenset()):
            source = origin.resolve(strict=True)
            require(any(source.is_relative_to(root) for root in allowed), "runtime-source-outside-approved-roots")
            if source.is_dir():
                require(source not in ancestors, "runtime-symlink-cycle")
                for item in sorted(source.iterdir()):
                    if item.name in skip or item.suffix in {".pyc", ".pyo"}:
                        continue
                    if rel == Path("odoo/addons") and item.name != "__init__.py":
                        continue
                    add(item, rel / item.name, ancestors | {source})
                return
            require(source.is_file() and not rel.is_absolute() and ".." not in rel.parts, "invalid-runtime-member")
            key = rel.as_posix()
            require(key not in hashes, "duplicate-runtime-member")
            mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
            checksum = digest(source)
            info = tarfile.TarInfo(key)
            info.mode, info.size = mode, source.stat().st_size
            with source.open("rb") as incoming:
                bundle.addfile(info, incoming)
            hashes[key] = [info.size, checksum, mode]
            provenance[key] = str(source)

        for name in ("odoo-bin", "odoo", "requirements.txt", "LICENSE", "COPYRIGHT", "README.md"):
            add(runtime / name, Path(name))
        for name, (origin, version, license_) in sorted(providers.items()):
            require(license_ != "OEEL-1" and name.isidentifier(), "invalid-community-provider")
            rel = Path("odoo/addons" if name == "base" else "addons") / name
            add(Path(origin), rel)
    extract_runtime(archive, target, hashes)
    # Verify original bytes again after extraction, including revisions supplied by private addon overlays.
    require(all(digest(Path(provenance[key])) == value[1] for key, value in hashes.items()), "source-runtime-drift")
    serial = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    (output / "runtime-members.json").write_bytes(serial)
    (output / "effective-providers.json").write_text(json.dumps(providers, sort_keys=True, indent=2))
    return {"archive_sha256": digest(archive), "manifest_sha256": hashlib.sha256(serial).hexdigest(),
            "providers": len(providers), "files": len(hashes), "expanded_bytes": sum(v[0] for v in hashes.values())}
