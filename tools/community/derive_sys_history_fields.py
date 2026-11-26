"""Compose the SyS first-initialization declarations with a reviewed free OCA overlay."""

import argparse
import ast
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from build_numeric_input_engine import hashes, require, seal, sha
from original_history_engine_contract import _snapshot


# The pristine pinned OCA files and the reviewed storage derivations differ
# in name translation, original labels and numeric precision. Keep those edits.
PINS = {
    ("payroll", "models/hr_payslip_input.py"): {
        "6122b5e76c6744530b366868226cee82f9a81de4db50412b5e335774d5413239",
        "2f21398754df6b55c0536bf212133c1af377e573d3b815be4decce0604c41c9e"},
    ("payroll", "models/hr_payslip_worked_days.py"): {
        "4fcb55c9df4e2b2e04730aaf8dec6d6706c655426d7e0e6a3b068ee3165ce777",
        "c6d7d746fc893f8c69e0ad6507e9ed91d2012c22a8bcaa36aa2253c2a9ed513a"},
    ("payroll", "models/hr_payslip_line.py"): {
        "68f23f57b04976099d8f8e0322861e6cd63ebc139eb618d19fcab3ef3916f2c3",
        "7c3197d64ca4677d40a7f141289f315d192498c2c3de1294162058d101efa4ec"},
    ("payroll_account", "models/hr_payslip_run.py"): {
        "48ec6dbac69646f8d9e1d2c3b3ca8ba239790612e163db97f5abec9f91bb157a"},
}

CODE = b'    code = fields.Char(\n        required=True,'
ORDER = b'    _order = "contract_id, sequence"\n'
JOURNAL = b'''        required=True,
        default=lambda self: self.env["account.journal"].search(
            [("type", "=", "general")], limit=1
        ),
'''
EDITS = {
    "models/hr_payslip_input.py": (CODE, CODE.replace(b"True", b"False")),
    "models/hr_payslip_worked_days.py": (CODE, CODE.replace(b"True", b"False")),
    "models/hr_payslip_line.py": (ORDER, ORDER + b'''
    condition_select = fields.Selection(required=False, default=None)
    amount_select = fields.Selection(required=False, default=None)
    condition_python = fields.Text(required=False, default=None)
'''),
    "models/hr_payslip_run.py": (JOURNAL, b'''        required=False,
        default=None,
        ondelete="restrict",
        check_company=True,
'''),
}


def plan(modules):
    """Input comes from the caller's verified engine. Never read a database or master."""
    require(set(modules) == {"payroll", "payroll_account"}, "Both OCA providers are required")
    result = {module: files.copy() for module, files in modules.items()}
    for files in result.values():
        require(ast.literal_eval(files["__manifest__.py"].decode())["license"] == "LGPL-3",
                "Only the reviewed free OCA providers are supported")
    for (module, path), pins in PINS.items():
        body = result[module][path]
        require(sha(body) in pins, "Unreviewed OCA field source: " + path)
        before, after = EDITS[path]
        require(body.count(before) == 1, "Missing unique OCA declaration: " + path)
        result[module][path] = body.replace(before, after)
        ast.parse(result[module][path])
    return result


def build(source, output):
    source, output = source.resolve(strict=True), output.resolve()
    private = (Path("/opt/steps-validation"), Path("/srv/odoo-data/steps-anchor-validation"))
    require(any(output.is_relative_to(path) for path in private) and not output.exists()
            and not output.is_relative_to(source), "A new private output directory is required")
    modules = {}
    for name in ("payroll", "payroll_account"):
        source_module = source / name
        manifest = source_module / "__manifest__.py"
        require(not source_module.is_symlink() and not manifest.is_symlink()
                and ast.literal_eval(manifest.read_text())["license"] == "LGPL-3",
                "Free provider manifest required before reading source")
        modules[name] = _snapshot(source_module)
    candidate = plan(modules)
    receipt = {"original": {name: seal(hashes(files)) for name, files in modules.items()},
               "derived": {name: seal(hashes(files)) for name, files in candidate.items()},
               "changed_files": [f"{module}/{path}" for module, path in PINS]}
    with TemporaryDirectory(dir=output.parent) as tmp:
        stage = Path(tmp) / "engine"
        for module, files in candidate.items():
            for name, body in files.items():
                path = stage / module / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            require(_snapshot(stage / module) == files, "Incomplete SyS engine overlay")
        (stage / "sys-history-fields.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        os.rename(stage, output)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), sort_keys=True))
