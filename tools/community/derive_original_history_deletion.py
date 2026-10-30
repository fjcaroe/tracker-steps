"""Two pinned LGPL OCA field policies, before first initialization.

Use only in the package carrying the real API draft-deletion guard. This is a
pure file derivation, not a database migration, history writer or native engine.
"""
import ast
import hashlib
from pathlib import Path


PIN = "4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e"
FILE = "models/hr_payslip.py"
SOURCE_SHA256 = "fe258058d682ab43d03d24cdd1d80966f45a955952c0e6bd0c2351488ae89acd"
POLICIES = {"company_id": {"required": True, "ondelete": "restrict"},
    "payslip_run_id": {"ondelete": "cascade"}}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def _calls(body):
    tree = ast.parse(body.decode("utf-8"))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HrPayslip"]
    require(len(classes) == 1, "Unique pinned real OCA payslip class required")
    result = {}
    for name in POLICIES:
        nodes = [node for node in classes[0].body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
        require(len(nodes) == 1 and isinstance(nodes[0].value, ast.Call), "Unique original payslip relation required")
        call = nodes[0].value
        require(isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "fields" and call.func.attr == "Many2one", "Actual Many2one declaration required")
        result[name] = call
    return tree, result


def plan_history_deletion(files):
    """Return module-relative bytes and provenance; never mutate the caller."""
    spec = ast.literal_eval(files["__manifest__.py"].decode("utf-8-sig"))
    require(spec.get("license") == "LGPL-3", "Only the pinned LGPL OCA payroll provider is admitted")
    body = files[FILE]
    require(sha(body) == SOURCE_SHA256, "Pinned real OCA payslip source differs")
    before, calls = _calls(body)
    expected_targets = {"company_id": "res.company", "payslip_run_id": "hr.payslip.run"}
    candidate = body
    for name, policies in POLICIES.items():
        call = calls[name]
        require(len(call.args) == 1 and isinstance(call.args[0], ast.Constant)
            and call.args[0].value == expected_targets[name], "Original relation target differs")
        require(not any(item.arg in policies for item in call.keywords), "Original deletion policy was already changed")
        prefix = ('    ' + name + ' = fields.Many2one(\n        "' + expected_targets[name] + '",\n').encode()
        require(candidate.count(prefix) == 1, "Pinned relation layout differs")
        addition = b"".join(('        ' + key + '=' + repr(value) + ',\n').encode() for key, value in policies.items())
        candidate = candidate.replace(prefix, prefix + addition, 1)
    after, calls = _calls(candidate)
    # Removing precisely the two declared policies must recover the complete
    # original AST. No method, domain, default, amount or unrelated field changes.
    for name, policies in POLICIES.items():
        call = calls[name]
        observed = {item.arg: ast.literal_eval(item.value) for item in call.keywords if item.arg in policies}
        require(observed == policies, "Derived original deletion policies differ")
        call.keywords = [item for item in call.keywords if item.arg not in policies]
    require(ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False),
        "Unrelated OCA code changed during original deletion derivation")
    result = dict(files)
    result[FILE] = candidate
    proof = {"schema": 1, "profile": "original-payslip-company-and-run-deletion", "oca_pin": PIN,
        "license": "LGPL-3", "file": FILE, "source_sha256": sha(body), "derived_sha256": sha(candidate),
        "builder_sha256": sha(Path(__file__).read_bytes()), "policies": {name: dict(values) for name, values in POLICIES.items()},
        "only_supported_field_keywords_changed": True, "requires_actual_api_draft_deletion_guard": True,
        "api_minimum_version": "18.0.1.17.0", "guard_model_file": "models/original_history_deletion.py",
        "database_accessed": False, "source_checkout_changed": False, "historical_rows_rewritten": False,
        "paid_payroll_recalculated": False, "native_equivalence_certified": False, "integral_conversion": False}
    return result, proof
