"""Private LGPL OCA derivation: unbounded NUMERIC input storage from first init.

Only one supported fields.Float keyword changes. The real engine, models,
methods, views, data, ACL and source checkout remain intact. No DB access.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

PIN = "4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e"
MODULE = "payroll"
FILE = "models/hr_payslip_input.py"
REPORT = "oca-input-numeric-derivation.json"
BEFORE = b"    amount = fields.Float(\n"
AFTER = BEFORE + b"        digits=False,\n"


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def hashes(files):
    return {name: sha(body) for name, body in sorted(files.items())}


def seal(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def plan(files):
    declaration = ast.literal_eval(files["__manifest__.py"].decode("utf-8-sig"))
    require(declaration.get("license") == "LGPL-3", "Only the reviewed free OCA engine is admitted")
    for name in declaration.get("data", []) + declaration.get("demo", []):
        require(name in files and not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts, "Unresolved engine data")
    body = files[FILE]
    require(body.count(BEFORE) == 1 and b"digits=" not in body, "Pinned input declaration drift")
    tree = ast.parse(body.decode())
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HrPayslipInput"]
    require(len(classes) == 1, "Real input class missing")
    assignments = [node for node in classes[0].body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "amount" for t in node.targets)]
    require(len(assignments) == 1 and isinstance(assignments[0].value, ast.Call), "Unique real amount field required")
    call = assignments[0].value
    require(isinstance(call.func, ast.Attribute) and call.func.attr == "Float" and isinstance(call.func.value, ast.Name) and call.func.value.id == "fields", "Real Float declaration required")
    require(not any(k.arg in ("digits", "default", "compute", "store") for k in call.keywords), "Existing precision/default policy cannot be replaced")
    candidate = dict(files); candidate[FILE] = body.replace(BEFORE, AFTER, 1)
    return candidate


def source_files(oca):
    oca = Path(oca).resolve()
    command = ["git", "-c", "safe.directory=" + str(oca), "-C", str(oca)]
    require(subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip() == PIN, "OCA pin drift")
    require(not subprocess.check_output(command + ["status", "--porcelain", "--untracked-files=no"], text=True).strip(), "Tracked OCA source drift")
    # Check licensing before reading any engine runtime body.
    declaration = ast.literal_eval(subprocess.check_output(command + ["show", "HEAD:payroll/__manifest__.py"]).decode("utf-8-sig"))
    require(declaration.get("license") == "LGPL-3", "Nonfree engine refused")
    names = subprocess.check_output(command + ["ls-files", "-z", "--", MODULE]).decode().split("\0")
    result = {}
    for name in filter(None, names):
        value = PurePosixPath(name)
        require(value.parts[0] == MODULE and not value.is_absolute() and ".." not in value.parts, "Unsafe tracked engine path")
        path = oca / name
        require(path.is_file() and not path.is_symlink(), "Tracked engine file unavailable")
        body = path.read_bytes()
        require(body == subprocess.check_output(command + ["show", "HEAD:" + name]), "Engine file differs from pinned Git blob")
        result[value.relative_to(MODULE).as_posix()] = body
    require(FILE in result, "Real pinned input implementation missing")
    return result


def report_for(original, candidate):
    report = {"schema": 1, "profile": "oca-unbounded-numeric-input", "module": MODULE,
        "license": "LGPL-3", "oca_pin": PIN, "builder_sha256": sha(Path(__file__).read_bytes()),
        "source_files": hashes(original), "candidate_files": hashes(candidate),
        "changed_files": [FILE], "supported_keyword": {"field": "hr.payslip.input.amount", "digits": False},
        "new_digits_rounding": False, "database_accessed": False, "historical_conversion": False,
        "financial_certified": False, "source_checkout_changed": False}
    report["seal_sha256"] = seal(report)
    return report


def verify(oca, output):
    original = source_files(oca); candidate = plan(original)
    output = Path(output).resolve()
    actual = {p.relative_to(output / MODULE).as_posix(): p.read_bytes() for p in (output / MODULE).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    require(hashes(actual) == hashes(candidate), "Derived engine bytes drift")
    report = json.loads((output.parent / REPORT).read_text())
    require(report == report_for(original, candidate), "Derived engine provenance drift")
    return report


def build(oca, output):
    original = source_files(oca); candidate = plan(original)
    output = Path(output).resolve()
    require(output.is_relative_to(Path("/opt/steps-validation")) and not output.exists(), "New private engine output required")
    for name, body in candidate.items():
        path = output / MODULE / name; path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "wb") as stream:
            stream.write(body)
    report = report_for(original, candidate)
    with os.fdopen(os.open(output.parent / REPORT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(report, stream, indent=2)
    verify(oca, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oca", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    report = verify(args.oca, args.output) if args.verify else build(args.oca, args.output)
    print("OCA_NUMERIC_INPUT_DERIVATION_VERIFIED", len(report["candidate_files"]), "files; one supported field keyword")


if __name__ == "__main__":
    main()
