"""Keep the original signed recovery kit and the complete operator evidence in its existing Windows disk allowance."""
import argparse
import ctypes
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import tarfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def allocated(path):
    high = ctypes.c_ulong()
    small = ctypes.windll.kernel32.GetCompressedFileSizeW(str(path),ctypes.byref(high))
    if small == 0xffffffff and ctypes.windll.kernel32.GetLastError():
        raise OSError("Cannot establish physical disk usage")
    return small + (high.value << 32)


def publish(evidence, kit):
    ballot = json.loads((evidence/"final.json").read_bytes())
    release = (kit/"release.json").read_bytes()
    if not ballot["complete"] or ballot["release"] != sha(release):
        raise ValueError("Operator receipt does not belong to the signed release")
    names = {"registry.json", "restored.json", "payroll.json", "exports.json", "documents.json", "invoices.json",
             "final.json", "colors.json", "verified-userspace.json"}
    names.update(s+"-source-members.json.gz" for s in ("pg","odoo","extras","print"))
    for row in json.loads((evidence/"invoices.json").read_bytes())["printed"]:
        name = "invoices/%d-%s.pdf" % (row["actor"],row["kind"])
        if Path(name).parent != Path("invoices") or sha((evidence/name).read_bytes()) != row["sha256"]:
            raise ValueError("Different private financial report")
        names.add(name)
    if names != {p.relative_to(evidence).as_posix() for p in evidence.rglob("*") if p.is_file()}:
        raise ValueError("Unexpected private evidence set")
    contents = {name:(evidence/name).read_bytes() for name in names}
    contents["verification.json"] = json.dumps({k:sha(v) for k,v in contents.items()},sort_keys=True).encode()
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw,mode="w") as archive:
        for name,data in sorted(contents.items()):
            info=tarfile.TarInfo(name)
            info.size,info.mode=len(data),0o600
            archive.addfile(info,io.BytesIO(data))
    packed=gzip.compress(raw.getvalue(), compresslevel=9, mtime=0)
    target=kit.parent/"operator-acceptance.tar.gz"
    if not target.exists():
        original=kit/"filestore-delta.tar"
        expected=json.loads(release)["files"][original.name]
        if sha(original.read_bytes()) != expected:
            raise ValueError("Unexpected existing filestore supplement")
        # NTFS transparent compression preserves every source byte and the existing signed manifest.
        if shutil.disk_usage(kit).free < 3 * 1024**3 + len(packed):
            subprocess.run(["compact","/C","/F",str(original)],check=True,stdout=subprocess.DEVNULL)
            if sha(original.read_bytes()) != expected:
                raise ValueError("Sealed bytes differ after filesystem compression")
            # The target workstation uses 4 KiB clusters. Reserve one extra allocation for its directory entry.
            available=math.ceil(original.stat().st_size/4096)*4096 - allocated(original)
            if math.ceil(len(packed)/4096)*4096 + 4096 > available:
                raise ValueError("Insufficient space within the existing 193 product allowance")
        with target.open("xb") as stream:
            stream.write(packed)
    if target.read_bytes()!=packed:
        raise ValueError("Existing immutable operator evidence differs")
    with tarfile.open(target,"r:gz") as archive:
        observed={member.name:archive.extractfile(member).read() for member in archive}
    if observed!=contents:
        raise ValueError("The durable off-host evidence cannot be independently reproduced")
    print(len(packed),sha(packed))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("evidence",type=Path)
    p.add_argument("kit",type=Path)
    a=p.parse_args()
    publish(a.evidence,a.kit)
