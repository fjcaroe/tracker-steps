"""Verify every original attachment byte on the workstation and export the four private report outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile

from restore_local_fiscal_print import DB, WORK, ROOT, STORE, pg, sha


def finish(source, out):
    receipt = json.loads((WORK / "proofs/rendered.json").read_bytes())
    if receipt["modules"] != 193 or len(receipt["protected"]) != 21:
        raise ValueError("Completed schema, row and permission checks required")
    original = {}
    for filename in ("filestore.tar", "filestore-extra.tar"):
        with tarfile.open(source / filename, "r|") as bundle:
            for member in bundle:
                if not member.isfile() or member.name in original:
                    raise ValueError("Unexpected entry in the sealed object archive")
                with bundle.extractfile(member) as stream:
                    original[member.name] = [member.size, hashlib.file_digest(stream, "sha256").hexdigest()]
    manifest = json.loads((source / "filestore-physical.json").read_bytes())
    fingerprint = hashlib.sha256(json.dumps(original, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fingerprint != manifest["tree_sha256"] or len(original) != manifest["all_files"]:
        raise ValueError("Unknown original filestore tree")
    actual = {p.relative_to(STORE).as_posix(): [p.stat().st_size, sha(p)] for p in STORE.rglob("*") if p.is_file()}
    if any(actual.get(k) != v for k, v in original.items()):
        raise ValueError("An original physical attachment or checklist marker has changed")
    objects = set(pg("psql", "-qXAt", "-d", DB, "-c", "SELECT DISTINCT store_fname FROM ir_attachment "
                     "WHERE store_fname IS NOT NULL AND store_fname<>'' ORDER BY store_fname",
                     capture_output=True, text=True).stdout.splitlines())
    if not objects <= actual.keys():
        raise ValueError("A referenced attachment is missing")
    new = sorted(actual.keys() - original.keys())
    for name in new:
        if not re.fullmatch(r"(?:checklist/)?([a-f0-9]{2})/[a-f0-9]{40}", name):
            raise ValueError("Unknown new physical file")
        file = STORE / name
        blob = file.read_bytes()
        if name.startswith("checklist/"):
            if blob:
                raise ValueError("A filestore checklist marker has contents")
        elif hashlib.sha1(blob).hexdigest() != file.name or b"{" not in blob or b"}" not in blob:
            raise ValueError("Unexpected new object outside the public print stylesheets")
    evidence = {**receipt, "original_objects_and_markers": len(original), "source_tree_sha256": fingerprint,
                "original_physical_changes": 0, "final_referenced_objects": len(objects), "final_physical": len(actual),
                "added_referenced_assets": len(objects.intersection(new)),
                "added_unreferenced_assets": len([n for n in new if n not in objects and not n.startswith("checklist/")]),
                "added_checklist_markers": len([n for n in new if n.startswith("checklist/")])}
    out.mkdir(exist_ok=True, mode=0o700)
    pdfs = out / "candidate-pdfs"
    pdfs.mkdir(exist_ok=True, mode=0o700)
    action = json.loads((WORK / "proofs/pdf.json").read_bytes())
    for entry in action["printed"]:
        p = ROOT / entry["private_file"].lstrip("/")
        name = str(entry["actor"]) + "-" + entry["kind"] + ".pdf"
        if (p.name != name or not p.resolve(strict=True).is_relative_to(WORK / "data")
                or sha(p) != entry["sha256"]):
            raise ValueError("Unexpected private invoice output")
        target = pdfs / name
        if target.exists() and sha(target) != entry["sha256"]:
            raise ValueError("Refusing to replace a different private report")
        shutil.copyfile(p, target)
    for source_name, destination in (("proofs/pdf.json", "invoice-pdf.json"), ("proofs/restored.json", "restored.json"),
                                     ("proofs/installed.json", "installed.json"), ("installed-rows.json", "installed-rows.json"),
                                     ("rendered-rows.json", "rendered-rows.json")):
        shutil.copyfile(WORK / source_name, out / destination)
    (out / "physical-after.json").write_text(json.dumps(evidence, sort_keys=True))
    print(json.dumps({k: evidence[k] for k in ("original_objects_and_markers", "source_tree_sha256", "final_physical",
                                               "added_referenced_assets", "added_unreferenced_assets", "added_checklist_markers")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("custody", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    finish(args.custody, args.out)
