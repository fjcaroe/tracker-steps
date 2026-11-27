"""Persist the final recovery kit by reusing verified FG bytes and reconstruct the exact PostgreSQL dump."""
import argparse
from compression import zstd
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from seal_local_sys_193 import INDEX, MEM, ROOT, save, sha, verify

DUMP = "source.dump"
PATCH = "source.dump.zstpatch"


def materialize(custody, kit, recovery):
    transport = json.loads((kit/"transport.json").read_bytes())
    if transport["base_index"] != INDEX or sha(custody/"verified-local-members.json") != INDEX:
        raise ValueError("Unknown FG reference")
    if sha(custody/DUMP) != transport["base_sql"] or sha(kit/PATCH) != transport["delta_sql"]:
        raise ValueError("Unverified input to SQL reconstruction")
    dictionary = zstd.ZstdDict((custody/DUMP).read_bytes(), is_raw=True)
    raw = zstd.decompress((kit/PATCH).read_bytes(), zstd_dict=dictionary.as_prefix)
    if hashlib.sha256(raw).hexdigest() != transport["restored_dump"]:
        raise ValueError("Reconstructed SQL differs")
    recovery.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, digest in transport["members"].items():
        if Path(name).name != name or sha(kit/name) != digest:
            raise ValueError("A kit component differs: " + name)
        shutil.copyfile(kit/name, recovery/name)
    (recovery/DUMP).write_bytes(raw)
    verify(recovery,custody)
    print("RECONSTRUCTED", len(raw), transport["restored_dump"], sha(recovery/"release.json"))


def store(custody, kit):
    sealed = MEM/"sealed"
    release = verify(sealed,custody)
    original = custody/DUMP
    captured = sealed/DUMP
    if sha(original) != "435bd9ba963688ce202107c1f63351080e55296ff25a4bdc1d23f2f0fb76bf83":
        raise ValueError("Unknown predecessor SQL")
    dictionary = zstd.ZstdDict(original.read_bytes(),is_raw=True)
    params = {zstd.CompressionParameter.compression_level:5, zstd.CompressionParameter.window_log:26,
              zstd.CompressionParameter.enable_long_distance_matching:1}
    delta = zstd.compress(captured.read_bytes(),options=params,zstd_dict=dictionary.as_prefix)
    paths = sorted(p for p in sealed.iterdir() if p.is_file() and p.name != DUMP)
    expected = len(delta) + sum(p.stat().st_size for p in paths) + 1024 * 1024
    kit.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if kit.exists():
        materialize(custody,kit,MEM/"from-durable-kit")
        return
    if not kit.parent.resolve().is_relative_to("/mnt/c") or shutil.disk_usage(kit.parent).free - expected < 3 * 1024**3:
        raise ValueError("The workstation must keep three physical GiB free after writing the new kit")
    with tempfile.TemporaryDirectory(dir=kit.parent,prefix="building-193-") as tmp:
        draft = Path(tmp)/"verified"
        draft.mkdir(mode=0o700)
        (draft/PATCH).write_bytes(delta)
        for path in paths:
            shutil.copyfile(path,draft/path.name)
        save(draft/"transport.json",{"base_index":INDEX,"base_sql":sha(original),"delta_sql":sha(draft/PATCH),
             "restored_dump":release["files"][DUMP],"members":{p.name:sha(p) for p in paths}})
        materialize(custody,draft,MEM/"from-durable-kit")
        draft.rename(kit)
    materialize(custody,kit,MEM/"from-durable-kit")
    print("DURABLE",sum(f.stat().st_size for f in kit.iterdir()),sha(kit/"transport.json"))


def collect(custody, kit, memory_only=False):
    root = kit.parent
    source = MEM / "proofs"
    final = json.loads((source / "final.json").read_bytes())
    if not final["complete"] or final["release"] != sha(kit / "release.json") or not final["source_control_unchanged"]:
        raise ValueError("A successful independent recovery is required")
    if memory_only:
        evidence = MEM / "workstation-evidence"
    else:
        if shutil.disk_usage(root).free < 3 * 1024**3 + 3 * 1024**2:
            raise ValueError("Use --memory-only while the workstation reserve is low")
        evidence = root / "acceptance"
    evidence.mkdir(mode=0o700, exist_ok=True)
    pdf = evidence / "invoices"
    pdf.mkdir(mode=0o700, exist_ok=True)
    for name in ("registry", "restored", "payroll", "exports", "documents", "invoices", "final"):
        shutil.copyfile(source / (name + ".json"), evidence / (name + ".json"))
    system = {}
    for stage in ("pg","odoo","extras","print"):
        signed = ROOT / (stage + "-source-members.json")
        meta = json.loads(signed.read_bytes())
        if meta["stage"] != stage:
            raise ValueError("Unexpected public OS manifest")
        for name, (size, checksum, _) in meta["files"].items():
            file = ROOT / name
            if file.stat().st_size != size or sha(file) != checksum:
                raise ValueError("Changed Focal userspace file: " + name)
        system[stage] = {"count": len(meta["files"]), "sha256": sha(signed)}
        (evidence / (stage + "-source-members.json.gz")).write_bytes(gzip.compress(signed.read_bytes(), mtime=0))
    save(evidence / "verified-userspace.json", system)
    invoices = json.loads((evidence / "invoices.json").read_bytes())
    for row in invoices["printed"]:
        path = Path(row["private_file"])
        filename = str(row["actor"]) + "-" + row["kind"] + ".pdf"
        if (path.name != filename or not path.resolve(strict=True).is_relative_to(MEM / "data")
                or sha(path) != row["sha256"]):
            raise ValueError("Unexpected physical financial report")
        shutil.copyfile(path, pdf / filename)
    materialize(custody, kit, MEM / "from-durable-kit")
    if memory_only:
        # The workstation owner reads this folder through the private WSL distribution share.
        # Keep every other account out of it. The source copies stay under root permissions.
        uid = int(os.environ["SUDO_UID"]) if "SUDO_UID" in os.environ else 1000
        for base, dirs, files in os.walk(evidence):
            os.chown(base, uid, uid)
            os.chmod(base, 0o700)
            for name in files:
                file = Path(base)/name
                os.chown(file, uid, uid)
                file.chmod(0o600)
    print("OPERATOR_EVIDENCE", sha(evidence / "final.json"))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("store","materialize","collect"))
    p.add_argument("custody",type=Path)
    p.add_argument("kit",type=Path)
    p.add_argument("--recovery",type=Path,default=MEM/"from-durable-kit")
    p.add_argument("--memory-only", action="store_true", help="Collect private output in WSL RAM for the workstation user.")
    a=p.parse_args()
    if a.action=="store":
        store(a.custody,a.kit)
    elif a.action=="collect":
        collect(a.custody,a.kit,a.memory_only)
    else:
        materialize(a.custody,a.kit,a.recovery)
