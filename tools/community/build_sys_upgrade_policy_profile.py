"""Render the checked original policy seeds as Odoo update-preserving records on the SyS upgrade copy."""
import ast
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import tarfile

from lxml import etree

from audit_sys_upgrade_policy import audit
from custody_sys_previred_filestore import digest
from restore_sys_previred_pair import require


def wrap_rules(file, names):
    xml = etree.parse(str(file))
    changed = set()
    for node in xml.xpath('//record[@model="res.groups" or @model="ir.rule"]'):
        if node.xpath('ancestor-or-self::*[@noupdate="1"]'):
            continue
        require(node.get("id") in names and node.getparent().tag in ("odoo", "data"), "unexpected-policy-seed")
        parent = node.getparent()
        wrapper = etree.Element("data", noupdate="1")
        parent.replace(node, wrapper)
        wrapper.append(node)
        changed.add(node.get("id"))
    if changed:
        xml.write(str(file), encoding="UTF-8", xml_declaration=True)
    return changed


def render_access(source, target, names):
    root = etree.Element("odoo")
    data = etree.SubElement(root, "data", noupdate="1")
    changed = set()
    with source.open(encoding="utf-8-sig", newline="") as incoming:
        for row in csv.DictReader(incoming):
            key = row.pop("id")
            require(key in names and key not in changed, "unexpected-access-identity")
            changed.add(key)
            record = etree.SubElement(data, "record", id=key, model="ir.model.access")
            for key, raw in row.items():
                if key.endswith((":id", "/id")):
                    field = etree.SubElement(record, "field", name=key[:-3])
                    if raw:
                        field.set("ref", raw)
                    else:
                        field.set("eval", "False")
                elif key.startswith("perm_"):
                    require(raw in ("0", "1"), "unsupported-access-flag")
                    etree.SubElement(record, "field", name=key, eval=str(raw == "1"))
                else:
                    require(key == "name", "unsupported-access-column")
                    etree.SubElement(record, "field", name=key).text = raw
    etree.ElementTree(root).write(str(target), encoding="UTF-8", xml_declaration=True, pretty_print=True)
    return changed


def fingerprint(profile):
    files = {f.relative_to(profile).as_posix(): digest(f) for f in sorted(profile.rglob("*")) if f.is_file()}
    serial = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return len(files), hashlib.sha256(serial).hexdigest()


def build(db, sealed, target, modules):
    require(not target.exists(), "profile-output-exists")
    core = sealed / "runtime"
    schema = etree.RelaxNG(etree.parse(str(core / "odoo/import_xml.rng")))
    policies = audit(db, core, modules)
    total = sum(len(records) for records in policies.values())
    require(total == 40 and all(not p["differences"] for records in policies.values() for p in records.values()),
            "existing-original-acl-group-rule-differs")
    changes = {}
    with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
        profile = Path(temporary) / "profile"
        profile.mkdir(mode=0o755)
        for module, records in policies.items():
            if not records:
                continue
            origin = core / "addons" / module
            output = profile / module
            shutil.copytree(origin, output)
            manifest_file = output / "__manifest__.py"
            manifest_text = manifest_file.read_text()
            manifest = ast.literal_eval(manifest_text)
            names = {p["declared_id"] for p in records.values()}
            processed = set()
            updated = {}
            for name in manifest["data"]:
                file = output / name
                if file.name == "ir.model.access.csv":
                    require(manifest_text.count(name) == 1, "ambiguous-access-manifest")
                    alternate = file.with_name("sys_preserved_access.xml")
                    require(not alternate.exists(), "seed-file-exists")
                    processed.update(render_access(file, alternate, names))
                    schema.assertValid(etree.parse(str(alternate)))
                    manifest_text = manifest_text.replace(name, alternate.relative_to(output).as_posix())
                    updated[name] = digest(alternate)
                elif file.suffix == ".xml":
                    ids = wrap_rules(file, names)
                    if ids:
                        schema.assertValid(etree.parse(str(file)))
                        processed.update(ids)
                        updated[name] = digest(file)
            require(processed == names, "not-every-original-policy-seed-accounted-for")
            revised = ast.literal_eval(manifest_text)
            expected = dict(manifest, data=[str(Path(n).with_name("sys_preserved_access.xml"))
                                            if Path(n).name == "ir.model.access.csv" else n for n in manifest["data"]])
            require(revised == expected, "unexpected-manifest-change")
            manifest_file.write_text(manifest_text)
            changes[module] = {"records": records, "files": updated, "manifest": digest(manifest_file)}
        files, sha = fingerprint(profile)
        # copytree retains the upstream directory modes. Validation runs under the Odoo service identity.
        for directory in (profile, *(p for p in profile.rglob("*") if p.is_dir())):
            directory.chmod(0o755)
        for file in profile.rglob("*"):
            if file.is_file():
                file.chmod(0o755 if file.stat().st_mode & 0o111 else 0o644)
        profile.rename(target)
    return {"records": total, "modules": changes, "files": files, "sha256": sha}


def seal_profile(profile, target, expected):
    require(fingerprint(profile) == (expected["files"], expected["sha256"]), "profile-fingerprint-drift")
    with tarfile.open(target, "x") as output:
        for member in sorted(profile.rglob("*")):
            if member.is_dir():
                continue
            require(member.is_file() and not member.is_symlink(), "invalid-profile-member")
            info = tarfile.TarInfo(member.relative_to(profile).as_posix())
            info.size = member.stat().st_size
            info.mode = 0o755 if member.stat().st_mode & 0o111 else 0o644
            with member.open("rb") as source:
                output.addfile(info, source)
    with tarfile.open(target, "r|") as archive:
        files = {}
        for member in archive:
            require(member.isfile() and member.name not in files, "invalid-sealed-profile")
            with archive.extractfile(member) as data:
                files[member.name] = hashlib.sha256(data.read()).hexdigest()
    indexed = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    require(len(files) == expected["files"] and hashlib.sha256(indexed).hexdigest() == expected["sha256"],
            "archived-upgrade-package-differs")
    return {"archive_sha256": digest(target), "archive_bytes": target.stat().st_size,
            "files": expected["files"], "members_sha256": expected["sha256"]}
