"""Reproduce the real AGPL candidate without its two salary seed XML files.

One unpaid-type seed link is deferred explicitly until original adoption. No
database access, configuration import, XML-ID reassignment or alternative
payroll model is implemented. Runtime uses the unchanged pinned derivation.
Missing references fail before sealing this non-operational bootstrap.
"""
import argparse
import ast
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


MODULE = "l10n_cl_simpledigital_payroll"
OMIT = ("data/hr_salary_structure.xml", "data/hr_salary_rule.xml")
DEFER_FILE = "data/hr_work_entry_type.xml"
DEFER_TYPE = MODULE + ".work_entry_type_unpaid_cl"
DEFER_STRUCTURE = MODULE + ".structure_chile"
PIN_COMMUNITY = "4b4efe68291d6def5bb7d2e1f2b829e0cda577d4"
PIN_OCA = "4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e"
SALARY_MODELS = {"hr.salary.rule", "hr.salary.rule.category", "hr.payroll.structure", "hr.payroll.structure.type", "hr.payslip.input.type"}
REPORT = "original-bootstrap-derivation.json"


class BootstrapError(ValueError):
    pass


def require(value, code):
    if not value:
        raise BootstrapError(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def snapshot(root):
    return {str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
        for path in sorted(root.rglob("*")) if path.is_file() and "__pycache__" not in path.parts}


def hashes(files):
    return {name: hashlib.sha256(value).hexdigest() for name, value in sorted(files.items())}


def _write_receipt(path, report):
    # Private from the instant of creation, including under an open umask.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(report, indent=2, sort_keys=True) + "\n")


def manifest(files):
    result = ast.literal_eval(files["__manifest__.py"].decode("utf-8-sig"))
    result.setdefault("license", "LGPL-3")  # official Odoo manifest default
    require(result.get("license") in ("AGPL-3", "LGPL-3"), "nonfree-runtime-rejected")
    for name in result.get("data", []) + result.get("demo", []):
        require(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts, "unsafe-manifest-path")
        require(name in files, "missing-manifest-file")
    return result


def qualify(value, module):
    return value if "." in value else module + "." + value


def loaded_python(files):
    """Follow actual package relative imports, excluding tests and unused files."""
    pending, seen = ["__init__.py"], set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        require(name in files, "missing-runtime-python-import")
        seen.add(name)
        tree = ast.parse(files[name].decode("utf-8-sig"))
        package = list(PurePosixPath(name).parent.parts)
        if package == ["."]:
            package = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            parent = package[:len(package) - node.level + 1]
            base = parent + (node.module.split(".") if node.module else [])
            candidates = [base] if node.module else []
            candidates += [base + alias.name.split(".") for alias in node.names if alias.name != "*"]
            for parts in candidates:
                for suffix in (".py", "/__init__.py"):
                    target = "/".join(parts) + suffix
                    if target in files:
                        pending.append(target)
                        break
    return sorted(seen)


def _python_references(tree, module, file, references):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else None
        if name not in {"ref", "_xmlid_lookup", "xmlid_to_res_id", "_xmlid_to_res_id", "get_object_reference"}:
            continue
        args = node.args[:2] if name == "get_object_reference" else node.args[:1]
        require(args and all(isinstance(value, ast.Constant) and isinstance(value.value, str) for value in args), "dynamic-xmlid-reference")
        value = ".".join(arg.value for arg in args) if name == "get_object_reference" else args[0].value
        optional = any(keyword.arg == "raise_if_not_found" and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is False for keyword in node.keywords)
        references.append({"xmlid": qualify(value, module), "file": file, "line": node.lineno,
            "kind": "python:" + name, "optional": optional})


def inventory(module, files, *, scan_references=True):
    """Definitions/references only. Never emit XML text, evals or formula code."""
    spec = manifest(files)
    definitions, references, master_records = {}, [], []
    for file in loaded_python(files):
        tree = ast.parse(files[file].decode("utf-8-sig"))
        if scan_references:
            _python_references(tree, module, file, references)
        # Official ir.model._reflect_models emits model XML IDs for modules
        # that create or extend a model. These are registry metadata, no rows.
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not any(isinstance(base, ast.Attribute) and base.attr in ("Model", "TransientModel", "AbstractModel") for base in node.bases):
                continue
            for assignment in node.body:
                if not isinstance(assignment, ast.Assign) or not any(isinstance(target, ast.Name) and target.id in ("_name", "_inherit") for target in assignment.targets):
                    continue
                try:
                    values = ast.literal_eval(assignment.value)
                except (ValueError, TypeError):
                    if scan_references:
                        raise BootstrapError("dynamic-model-identity") from None
                    continue
                if values is None or values is False:
                    continue
                require(isinstance(values, (str, list, tuple)) and all(isinstance(value, str)
                    for value in ([values] if isinstance(values, str) else values)), "invalid-model-identity")
                for model in ([values] if isinstance(values, str) else values):
                    definitions[module + ".model_" + model.replace(".", "_")] = "ir.model"
    for file in spec.get("data", []):
        if file.endswith(".xml"):
            tree = ET.fromstring(files[file])
            for node in tree.iter():
                ident = node.get("id")
                model = node.get("model")
                if ident and node.tag in ("record", "template", "menuitem", "act_window", "report"):
                    model = model or {"template": "ir.ui.view", "menuitem": "ir.ui.menu", "act_window": "ir.actions.act_window", "report": "ir.actions.report"}.get(node.tag)
                    definitions[qualify(ident, module)] = model
                    if model in SALARY_MODELS:
                        master_records.append({"file": file, "xmlid": qualify(ident, module), "model": model})
                if not scan_references:
                    continue
                for attribute in ("ref", "inherit_id", "parent", "action", "groups", "t-call", "t-inherit"):
                    value = node.get(attribute)
                    if not value:
                        continue
                    for item in value.split(",") if attribute == "groups" else [value]:
                        item = item.strip().lstrip("!")
                        if item.startswith("%("):
                            continue  # interpolation handled below
                        require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", item), "dynamic-xml-attribute-reference")
                        references.append({"xmlid": qualify(item, module), "file": file,
                            "kind": "xml:" + attribute, "optional": False})
                for attribute, value in node.attrib.items():
                    for match in re.finditer(r"%\(([A-Za-z_][A-Za-z0-9_.]*)\)[ds]", value):
                        references.append({"xmlid": qualify(match.group(1), module), "file": file,
                            "kind": "xml:interpolation", "optional": False})
                    if re.search(r"\bref\s*\(", value):
                        _python_references(ast.parse(value.strip(), mode="eval"), module, file, references)
                if node.tag == "field" and node.get("name") in ("code", "domain", "context") and node.text and re.search(r"\b(?:ref|_xmlid_lookup)\s*\(", node.text):
                    _python_references(ast.parse(node.text), module, file, references)
        elif file.endswith(".csv"):
            for number, row in enumerate(csv.DictReader(io.StringIO(files[file].decode("utf-8-sig"))), start=2):
                if row.get("id"):
                    definitions[qualify(row["id"], module)] = file.rsplit("/", 1)[-1][:-4]
                for column, value in row.items():
                    if scan_references and value and (column.endswith(":id") or column.endswith("/id")):
                        for item in value.split(","):
                            references.append({"xmlid": qualify(item.strip(), module), "file": file,
                                "line": number, "kind": "csv:" + column, "optional": False})
    return {"definitions": definitions, "references": references, "salary_records": master_records,
        "python_files": loaded_python(files)}


def plan_profile(normal_files, external_definitions):
    normal = manifest(normal_files)
    require(normal.get("license") == "AGPL-3" and normal.get("depends") == ["step_simpledigital_oca_base"], "normal-candidate-contract")
    require(not normal.get("demo"), "provider-demo-not-authorized")
    require(all(normal.get("data", []).count(name) == 1 for name in OMIT), "salary-seed-list-drift")
    files = dict(normal_files)
    spec = dict(normal, data=[name for name in normal["data"] if name not in OMIT])
    files["__manifest__.py"] = (repr(spec) + "\n").encode()
    for name in OMIT:
        files.pop(name)
    # This real retained type has one required link to the omitted structure.
    # Defer only that seed assignment; the relation/model and processing guards
    # remain real. No missing structure or original policy is manufactured.
    require(normal["data"].count(DEFER_FILE) == 1, "unpaid-seed-file-drift")
    tree = ET.fromstring(files[DEFER_FILE])
    owners = [node for node in tree.iter("record") if qualify(node.get("id", ""), MODULE) == DEFER_TYPE]
    require(len(owners) == 1 and owners[0].get("model") == "hr.work.entry.type", "unpaid-seed-owner-drift")
    assignments = [node for node in owners[0].findall("field") if node.get("name") == "unpaid_structure_ids"]
    require(len(assignments) == 1 and set(assignments[0].attrib) == {"name", "eval"}, "unpaid-seed-assignment-drift")
    expected = ast.dump(ast.parse("[(4, ref(%r))]" % DEFER_STRUCTURE, mode="eval"))
    require(ast.dump(ast.parse(assignments[0].get("eval"), mode="eval")) == expected, "unpaid-seed-expression-drift")
    pattern = rb"<field\b[^>]*\bname=[\"']unpaid_structure_ids[\"'][^>]*/>"
    matches = list(re.finditer(pattern, files[DEFER_FILE]))
    require(len(matches) == 1, "unpaid-seed-byte-span-drift")
    fragment = matches[0].group()
    files[DEFER_FILE] = files[DEFER_FILE][:matches[0].start()] + files[DEFER_FILE][matches[0].end():]
    before, after = inventory(MODULE, normal_files), inventory(MODULE, files)
    removed = set(before["definitions"]) - set(after["definitions"])
    require(DEFER_STRUCTURE in removed, "deferred-structure-is-not-an-omitted-seed")
    require(not after["salary_records"], "retained-salary-seed-record")
    optional_missing, resolved = [], []
    for reference in after["references"]:
        name = reference["xmlid"]
        if name in after["definitions"] or (name not in removed and name in external_definitions):
            resolved.append(reference)
        elif name in removed and reference["optional"]:
            optional_missing.append(reference)
        else:
            raise BootstrapError("orphan-reference:" + reference["file"] + ":" + name)
    return files, {"omitted_files": list(OMIT), "omitted_definitions": sorted(removed),
        "deferred_seed_assignment": {"file": DEFER_FILE, "record_xmlid": DEFER_TYPE, "field": "unpaid_structure_ids",
            "fragment": fragment.decode(), "fragment_sha256": hashlib.sha256(fragment).hexdigest(),
            "structure_xmlid": DEFER_STRUCTURE, "relation": "hr_payroll_structure_hr_work_entry_type_rel",
            "adopted": False, "original_policy_preserved_in_target": False,
            "must_adopt_before_chile_processing": True},
        "omitted_salary_records": before["salary_records"], "retained_salary_records": [],
        "references": resolved, "optional_missing_seed_references": optional_missing,
        "python_files": after["python_files"], "no_demo_required": True,
        "original_masters_imported": False, "original_aliases_guaranteed": False,
        "operational_payroll_package": False}


def dependencies(roots, entry="step_simpledigital_oca_base"):
    definitions, modules, visiting = {}, {}, set()
    def visit(name):
        if name in modules:
            return
        require(name not in visiting, "dependency-cycle")
        visiting.add(name)
        matches = [root / name for root in roots if (root / name / "__manifest__.py").is_file()]
        require(len(matches) == 1, "dependency-root-missing-or-ambiguous:" + name)
        # Inspect licensing before reading any runtime body. A wrong root must
        # not cause the resolver to inspect an Enterprise dependency's sources.
        declaration = ast.literal_eval((matches[0] / "__manifest__.py").read_text(encoding="utf-8-sig"))
        require(declaration.get("license", "LGPL-3") in ("AGPL-3", "LGPL-3"), "nonfree-runtime-rejected")
        files = snapshot(matches[0])
        spec = manifest(files)
        for parent in spec.get("depends", []):
            visit(parent)
        data = inventory(name, files, scan_references=False)
        definitions.update(data["definitions"])
        modules[name] = {"license": spec["license"], "files": hashes(files)}
        visiting.remove(name)
    visit(entry)
    return definitions, modules


def verify_snapshots(source_files, normal_files, profile_files, report, external_definitions, pin):
    """Pure verifier; snapshots are bytes, never executable evidence scripts."""
    require(report.get("schema") == 1 and report.get("profile") == "original-bootstrap-without-salary-seeds"
        and report.get("license") == "AGPL-3", "report-profile-contract")
    require(all(report.get(name) is False for name in ("database_accessed", "engine_converted", "financial_certified")), "report-cannot-certify-adoption")
    require(report.get("community_pin") == PIN_COMMUNITY and report.get("oca_pin") == PIN_OCA, "report-runtime-pin-drift")
    require(hashes(source_files) == pin["files"], "source-pin-drift")
    expected, closure = plan_profile(normal_files, external_definitions)
    require(hashes(expected) == hashes(profile_files), "profile-file-drift")
    require(report["source_files"] == hashes(source_files) and report["normal_files"] == hashes(normal_files), "source-snapshot-drift")
    require(report["profile_files"] == hashes(expected) and report["closure"] == closure, "profile-report-drift")
    require(report["seal_sha256"] == digest({key: value for key, value in report.items() if key != "seal_sha256"}), "report-seal-drift")
    return True


def build(source, output, *, dependency_roots, community_root, oca_root):
    source, output = Path(source).resolve(), Path(output).resolve()
    require(output.is_relative_to(Path("/opt/steps-validation")) and not output.exists(), "new-private-output-required")
    for root, pin in ((community_root, PIN_COMMUNITY), (oca_root, PIN_OCA)):
        command = ["git", "-c", "safe.directory=" + str(Path(root).resolve()), "-C", str(root)]
        actual = subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip()
        require(actual == pin, "runtime-git-pin-drift")
        require(not subprocess.check_output(command + ["status", "--porcelain", "--untracked-files=no"], text=True).strip(), "runtime-tracked-source-drift")
    base = Path(__file__).resolve().parent
    pin = json.loads((base / "simpledigital_runtime_source.json").read_text())
    source_files = {name: (source / name).read_bytes() for name in pin["files"]}
    require(hashes(source_files) == pin["files"], "source-pin-drift")
    roots = list(dict.fromkeys([Path(root).resolve() for root in dependency_roots]
        + [Path(community_root).resolve() / "addons", Path(community_root).resolve() / "odoo/addons", Path(oca_root).resolve()]))
    external, modules = dependencies(roots)
    # The unchanged normal builder is the sole runtime transformer. Its private
    # work directory is separate, so its receipt never overwrites another run.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="original-bootstrap-source-", dir=output.parent) as temporary:
        runtime = Path(temporary) / "addons"
        subprocess.run([sys.executable, str(base / "build_simpledigital_candidate.py"), "--source", str(source), "--output", str(runtime)],
            check=True, stdout=subprocess.DEVNULL)
        normal_files = snapshot(runtime / MODULE)
        profile, closure = plan_profile(normal_files, external)
        report = {"schema": 1, "profile": "original-bootstrap-without-salary-seeds", "license": "AGPL-3",
            "community_pin": PIN_COMMUNITY, "oca_pin": PIN_OCA, "source_files": hashes(source_files),
            "normal_builder_sha256": hashlib.sha256((base / "build_simpledigital_candidate.py").read_bytes()).hexdigest(),
            "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "normal_files": hashes(normal_files), "profile_files": hashes(profile), "dependencies": modules, "closure": closure,
            "database_accessed": False, "engine_converted": False, "financial_certified": False}
        report["seal_sha256"] = digest(report)
        require(not (output.parent / REPORT).exists(), "new-report-required")
        verify_snapshots(source_files, normal_files, profile, report, external, pin)
        for name, value in profile.items():
            path = output / MODULE / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
            path.chmod(0o644)
        # Only the newly owned runtime subtree is public to the Odoo role.
        # Its sibling receipt and the enclosing private evidence stay private.
        for directory in (output, *(path for path in output.rglob("*") if path.is_dir())):
            directory.chmod(0o755)
        _write_receipt(output.parent / REPORT, report)
    return report


def verify_reproduction(source, output, *, dependency_roots, community_root, oca_root):
    """Regenerate with trusted Git tools from exact sources, then compare bytes.

    Unlike the pure snapshot checker, this independently reruns the unchanged
    normal derivation; no code exported inside an evidence artifact is run.
    """
    output = Path(output).resolve()
    original = json.loads((output.parent / REPORT).read_text())
    with tempfile.TemporaryDirectory(prefix="original-bootstrap-reproduction-", dir=output.parent) as temporary:
        reproduced = build(source, Path(temporary) / "addons", dependency_roots=dependency_roots,
            community_root=community_root, oca_root=oca_root)
        require(reproduced == original, "reproduced-report-drift")
        require(hashes(snapshot(output / MODULE)) == original["profile_files"], "reproduced-profile-drift")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dependency-root", type=Path, action="append", required=True)
    parser.add_argument("--community-root", type=Path, required=True)
    parser.add_argument("--oca-root", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.source, args.output, dependency_roots=args.dependency_root,
        community_root=args.community_root, oca_root=args.oca_root)
    print("ORIGINAL_BOOTSTRAP_BUILT " + report["seal_sha256"])


if __name__ == "__main__":
    main()
