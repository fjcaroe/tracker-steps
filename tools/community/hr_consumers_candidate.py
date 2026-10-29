"""Build the private, real-engine HR consumer candidate without facade modules.

The tracked native manifests stay in place until integral identity conversion.
Only provider prerequisites and external engine view/menu/group references differ.
All owned XML IDs, Python models, fields, relation tables and ACL rows are retained.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil


MODULES = (
    "step_hr_contract_lifecycle", "step_hr_contract_lifecycle_simpledigital",
    "step_payroll_engine_transition", "steps_hr_payroll_correction",
)
XMLIDS = {
    "hr_payroll.group_hr_payroll_manager": "payroll.group_payroll_manager",
    "hr_payroll.view_hr_payslip_form": "payroll.hr_payslip_view_form",
    "hr_payroll.view_hr_payslip_tree": "payroll.hr_payslip_view_tree",
    "hr_payroll.menu_hr_payroll_employees_root": "step_simpledigital_oca_base.payroll_employees",
    "hr_payroll.menu_hr_payroll_report": "step_simpledigital_oca_base.payroll_reports",
    "hr_payroll.menu_hr_payroll_global_settings": "payroll.payroll_menu_configuration",
    "hr_work_entry_contract_enterprise.menu_hr_payroll_root": "payroll.payroll_menu_root",
}
DEPENDENCIES = {
    "hr_payroll": "step_simpledigital_oca_security",
    "hr_work_entry_contract_enterprise": "hr_work_entry_contract",
}


def build(source, output, *, community):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not str(output).replace("\\", "/").startswith("/opt/steps-validation/"):
        raise ValueError("The candidate must use a private /opt/steps-validation overlay")
    if any((output / name).exists() for name in MODULES):
        raise ValueError("Refusing to overwrite an existing candidate")
    evidence = {"community_candidate": community, "identity_conversion_accepted": False,
                "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "xmlid_map": XMLIDS if community else {}, "modules": {}}
    for name in MODULES:
        module = source / name
        manifest = ast.literal_eval((module / "__manifest__.py").read_text(encoding="utf-8-sig"))
        if manifest.get("license") != "LGPL-3":
            raise ValueError("Unexpected consumer license: " + name)
        files = {}
        target = output / name
        for path in sorted(module.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative = path.relative_to(module)
            dest = target / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            before = path.read_bytes()
            shutil.copyfile(path, dest)
            if community and path.suffix in (".xml", ".csv"):
                content = before.decode("utf-8-sig")
                for old, new in XMLIDS.items():
                    content = content.replace(old, new)
                if "hr_payroll." in content or "hr_work_entry_contract_enterprise." in content:
                    raise ValueError("Unclosed Enterprise XML reference: " + str(relative))
                dest.write_text(content, encoding="utf-8")
            files[str(relative)] = {"source": hashlib.sha256(before).hexdigest(),
                                    "candidate": hashlib.sha256(dest.read_bytes()).hexdigest()}
        if community:
            manifest["depends"] = list(dict.fromkeys(DEPENDENCIES.get(dep, dep) for dep in manifest["depends"]))
            (target / "__manifest__.py").write_text(repr(manifest) + "\n", encoding="utf-8")
            files["__manifest__.py"]["candidate"] = hashlib.sha256((target / "__manifest__.py").read_bytes()).hexdigest()
        evidence["modules"][name] = {"version": manifest["version"], "depends": manifest["depends"], "files": files}
    (output.parent / "hr-consumers-derivation.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--community", action="store_true")
    args = parser.parse_args()
    evidence = build(args.source, args.output, community=args.community)
    print("HR_CONSUMERS_CANDIDATE_BUILT " + ",".join(evidence["modules"]))


if __name__ == "__main__":
    main()
