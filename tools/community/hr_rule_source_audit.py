"""Inspect pinned rule provenance without exposing formula bodies or using Odoo."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET


ESSENTIAL = {"BASIC", "GROSS", "NET"}
OCA_REVISION = "4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e"


def records(root, names):
    result = []
    for name in names:
        path = root / name
        if path.suffix != ".xml":
            continue
        for record in ET.parse(path).getroot().iter("record"):
            model = record.get("model")
            if model not in ("hr.salary.rule", "hr.payroll.structure"):
                continue
            fields = {field.get("name"): field for field in record.findall("field")}
            item = {"file": name, "xmlid": record.get("id"), "model": model}
            for key in ("code", "parent_id", "category_id", "struct_id", "rule_ids"):
                if key in fields:
                    field = fields[key]
                    item[key] = {"text": field.text, "ref": field.get("ref"),
                                 "search": field.get("search"), "eval": field.get("eval")}
            formula = fields.get("amount_python_compute")
            if formula is not None:
                item["formula_sha256"] = hashlib.sha256((formula.text or "").encode()).hexdigest()
            result.append(item)
    return result


def audit(provider, oca):
    pin = json.loads(Path(__file__).with_name("simpledigital_runtime_source.json").read_text())
    manifest = ast.literal_eval((provider / "__manifest__.py").read_text(encoding="utf-8-sig"))
    assert manifest["license"] == pin["license"] == "AGPL-3"
    assert manifest["version"] == pin["version"]
    assert subprocess.run(["git", "-C", str(oca), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip() == OCA_REVISION
    subprocess.run(["git", "-C", str(oca), "diff", "--quiet", "HEAD", "--", "payroll"],check=True)
    assert all(hashlib.sha256((provider / name).read_bytes()).hexdigest() == digest
               for name, digest in pin["files"].items()), "Pinned AGPL runtime drift"
    oca_manifest = ast.literal_eval((oca / "payroll/__manifest__.py").read_text(encoding="utf-8-sig"))
    original = records(provider, manifest.get("data", []))
    production = records(oca / "payroll", oca_manifest.get("data", []))
    demo = records(oca / "payroll", oca_manifest.get("demo", []))
    def essentials(rows):
        return [item for item in rows if item["model"] == "hr.salary.rule"
                and item.get("code", {}).get("text") in ESSENTIAL]
    tree = ast.parse((oca / "payroll/models/hr_payroll_structure.py").read_text())
    structure = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HrPayrollStructure")
    parent_default = next(node for node in structure.body if isinstance(node, ast.FunctionDef) and node.name == "_get_parent")
    legacy_refs = [node.args[0].value for node in ast.walk(parent_default) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == "ref" and node.args
                   and isinstance(node.args[0], ast.Constant)]
    return {"auditor_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "provider_license": manifest["license"], "provider_version": manifest["version"], "oca_revision": OCA_REVISION,
            "source_files_pinned": len(pin["files"]), "provider_records": original,
            "provider_data_essential_rules": essentials(original),
            "oca_data_essential_rules": essentials(production), "oca_demo_essential_rules": essentials(demo),
            "oca_function_default_refs": legacy_refs,
            "demo_is_not_original_configuration": True, "formulas_exposed": False,
            "database_reads": False, "financial_certified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--oca", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert str(args.output.resolve()).startswith("/opt/steps-validation/")
    result = audit(args.provider, args.oca)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("HR_RULE_SOURCE_AUDIT provider-essential=%s oca-data-essential=%s oca-demo-essential=%s" % (
        len(result["provider_data_essential_rules"]), len(result["oca_data_essential_rules"]), len(result["oca_demo_essential_rules"])))


if __name__ == "__main__":
    main()
