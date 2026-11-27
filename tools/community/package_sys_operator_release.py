"""Assemble and verify a portable, deduplicated recovery directory for the final SyS payslip editor."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


FG_INDEX = "b033989da829ee87fa7233e3883f68cd1130eb52a4eb37ec8ebb8185e4d6c7e6"
KIT_INDEX = "38f4c970241ab4b82962b6581241ee5d6f5a639f732aa4feaf28940b3be350ae"
BASE = "35dfde4c6734efcb9575d7957381d06d1874326d245605b11d7d84e4f08942da"
MODULE = "e1f3d645ce6ca3b1c967114c72efb6db8c33c8e70c391d258caf6eb58ec27642"
TAR = "operator-form-" + MODULE + ".tar"
EVIDENCE = {"form.json":"f780d6ac33baa52ac9a921396d33644c50cb4c5d4cec39a27d1bce8b876e3a0d",
            "october.json":"879d0b45398ea4744585aa1730e0f40ff86f091b43856b5e46e7d6ead45c062e",
            "payroll.json":"088e4ffb3d54b7a1a9b91f835ddb9fe7568aafb94be2304a048744eea3b8c04f",
            "postflight.json":"f3733c1567cced4fbb6fe5774b68aecdbcf6fe9efa5afe6399f81d4a66eed652"}


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def needed_tools():
    root = Path(__file__).resolve().parent
    todo = {"package_sys_operator_release", "prepare_sys_payslip_form_trial", "seal_local_sys_193", "store_sys_193_release",
            "compare_sys_full_restore", "guard_sys_original_catalogue"}
    result = {}
    while todo:
        name = todo.pop()
        if name in result:
            continue
        path = root / (name + ".py")
        result[name] = path
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node, ast.ImportFrom) and node.module and (root / (node.module + ".py")).is_file():
                todo.add(node.module)
    return result.values()


def assemble(refs, target):
    fg, kit, operator = refs / "U43C/fiscal-payroll-documents", refs / "U46R/sealed", refs / "U48"
    assert sha(fg / "verified-local-members.json") == FG_INDEX and sha(kit / "transport.json") == KIT_INDEX
    sources = {}
    for name in [*read(fg / "verified-local-members.json"), "verified-local-members.json"]:
        assert Path(name).name == name
        sources["fg/" + name] = fg / name
    for name in [*read(kit / "transport.json")["members"], "source.dump.zstpatch", "transport.json"]:
        assert Path(name).name == name
        sources["base193/" + name] = kit / name
    for name in [TAR, *EVIDENCE]:
        sources["operator/" + name] = operator / name
    target.mkdir(exist_ok=True, parents=True)
    for name, source in sources.items():
        p = target / name
        p.parent.mkdir(exist_ok=True)
        if not p.exists():
            os.link(source, p)
        if sha(p) != sha(source):
            raise ValueError("Different existing component: " + name)
    for src in needed_tools():
        p = target / "tools" / src.name
        p.parent.mkdir(exist_ok=True)
        data = src.read_bytes().replace(b"\r\n",b"\n")
        if p.exists() and p.read_bytes() != data:
            raise ValueError("Recovery tool differs: " + p.name)
        p.write_bytes(data)
    files = {p.relative_to(target).as_posix():[p.stat().st_size,sha(p)] for p in target.rglob("*")
             if p.is_file() and p.name != "release.json" or p == target / "base193/release.json"}
    manifest = {"base193": BASE, "operator": MODULE, "months_and_companies": EVIDENCE["payroll.json"],
                "target": "COMMUNITY_SYS_PREVIRED_COHORT_20261127U48D", "modules": 193, "files": files}
    payload = json.dumps(manifest, sort_keys=True, separators=(",",":")).encode()
    index = target / "release.json"
    if index.exists() and index.read_bytes() != payload:
        raise ValueError("The existing final release differs")
    index.write_bytes(payload)
    verify(target)


def verify(target):
    index = read(target / "release.json")
    assert index["modules"]==193 and index["operator"]==MODULE and index["base193"]==BASE
    files = {p.relative_to(target).as_posix():p for p in target.rglob("*") if p.is_file() and p != target / "release.json"}
    if files.keys()!=index["files"].keys() or any([p.stat().st_size,sha(p)] != index["files"][n] for n,p in files.items()):
        raise ValueError("Recovery files differ from release")
    fg, kit = target / "fg", target / "base193"
    assert sha(fg/"verified-local-members.json")==FG_INDEX and sha(kit/"transport.json")==KIT_INDEX
    for name,entry in read(fg/"verified-local-members.json").items():
        assert index["files"]["fg/"+name]==[entry["bytes"],entry["sha256"]]
    transport,release=read(kit/"transport.json"),read(kit/"release.json")
    assert sha(kit/"release.json")==BASE and release["source_index"]==FG_INDEX
    assert sha(fg/"source.dump")==transport["base_sql"] and sha(kit/"source.dump.zstpatch")==transport["delta_sql"]
    assert transport["restored_dump"]==release["files"]["source.dump"]
    for name,checksum in {**transport["members"]}.items():
        assert sha(kit/name)==checksum
    for name,checksum in {TAR:MODULE, **EVIDENCE}.items():
        assert sha(target/"operator"/name)==checksum
    with tarfile.open(target/"operator"/TAR) as tar:
        manifest = ast.literal_eval(tar.extractfile("step_payroll_oca_sys_history/__manifest__.py").read().decode())
        assert len(tar.getmembers())==9 and manifest["version"]=="18.0.1.6.2"
    print("Verified", len(files), "files;", sha(target/"release.json"))


def restore(target):
    verify(target)
    if os.name!="posix" or os.getuid()!=0 or not os.path.ismount("/dev/shm"):
        raise ValueError("Recovery requires the isolated WSL Focal userspace")
    from restore_local_fiscal_print import RUNTIME, restore_sources
    from seal_local_sys_193 import MEM, restore as restore_base
    from store_sys_193_release import materialize
    fg, kit=target/"fg", target/"base193"
    if not (RUNTIME/"odoo-bin").is_file():
        restore_sources(fg)
    materialize(fg,kit,MEM/"from-durable-kit")
    restore_base(fg,MEM/"from-durable-kit")
    runner = target/"tools/prepare_sys_payslip_form_trial.py"
    env = dict(os.environ,SYS_PAYSLIP_FORM_FINAL="1")
    subprocess.run([sys.executable,str(runner),"--restore"],check=True,env=env)
    subprocess.run([sys.executable,str(runner),"--upgrade","--package",str(target/"operator"/TAR)],check=True,env=env)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=["assemble","verify","restore"])
    parser.add_argument("target",type=Path)
    parser.add_argument("--references",type=Path)
    args=parser.parse_args()
    if args.stage=="assemble":
        if not args.references:
            parser.error("assemble requires --references")
        assemble(args.references,args.target.resolve())
    else:
        {"verify":verify,"restore":restore}[args.stage](args.target.resolve())
