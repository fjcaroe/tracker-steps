"""Verify the three exact metadata edits made by closed-payroll protection.

Inputs are original/current ir_model_fields row lists, or identity snapshots
containing that key. Every original ID and property must remain exact except
the declared source-language messages below. Existing translations remain
byte-for-byte equivalent as JSON values; new fields can be added separately.
"""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path


MODEL = "hr.termination.correction.wizard"
SOURCE = Path("steps_hr_payroll_correction/wizard/hr_termination_correction_wizard.py")
EXPECTED = {
    "payslip_ids": {
        "help": "Liquidaciones cuyo período llega después de la fecha real y que todavía se pueden corregir (borrador o en verificación).",
    },
    "blocked_payslip_ids": {
        "help": "Validadas, pagadas o históricas: bloquean toda la operación. Nómina debe revisar la corrección sin modificar su historia.",
        "field_description": "Liquidaciones protegidas (revisión manual)",
    },
    "confirm": {
        "help": "Esta acción recalcula liquidaciones abiertas y elimina asistencia posterior al término. No tiene deshacer automático.",
    },
}
# Exact predecessor declarations, retained in canonical f56e221d. Admission
# never treats an arbitrary preexisting message as approved for replacement.
PREVIOUS = {
    "payslip_ids": {
        "help": "Liquidaciones cuyo período llega después de la fecha real y que todavía se pueden corregir (borrador, en verificación o confirmadas).",
    },
    "blocked_payslip_ids": {
        "help": "Ya se pagaron: no se tocan automáticamente. Corríjalas a mano si corresponde, evaluando el impacto en lo ya pagado.",
        "field_description": "Liquidaciones pagadas (requieren revisión manual)",
    },
    "confirm": {
        "help": "Esta acción desbloquea liquidaciones ya confirmadas y elimina asistencia validada. No tiene deshacer automático.",
    },
}


def source_contract():
    """Prove that allowed new messages are the actual field declarations."""
    path = Path(__file__).resolve().parents[2] / SOURCE
    raw = path.read_bytes()
    tree = ast.parse(raw.decode("utf-8-sig"))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HrTerminationCorrectionWizard"]
    if len(classes) != 1:
        raise AssertionError("Expected the actual correction wizard class")
    cls = classes[0]
    declarations = {node.targets[0].id: node.value for node in cls.body if isinstance(node, ast.Assign)
                    and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
    if ast.literal_eval(declarations["_name"]) != MODEL:
        raise AssertionError("Correction model identity changed")
    extracted = {}
    for name, properties in EXPECTED.items():
        node = declarations.get(name)
        kind = "Boolean" if name == "confirm" else "Many2many"
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "fields" and node.func.attr == kind):
            raise AssertionError("Correction field declaration changed: " + name)
        keywords = {item.arg: item.value for item in node.keywords}
        extracted[name] = {prop: ast.literal_eval(keywords["string" if prop == "field_description" else prop])
                           for prop in properties}
    if extracted != EXPECTED:
        raise AssertionError("Metadata admission messages differ from the tracked correction source")
    return {"path": SOURCE.as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "messages": extracted}


def _rows(value):
    rows = value["ir_model_fields"] if isinstance(value, dict) else value
    if not isinstance(rows, (list, tuple)) or not all(isinstance(row, dict) for row in rows):
        raise TypeError("Expected ir_model_fields rows from the identity contract")
    ids = [row.get("id") for row in rows]
    if any(type(ident) is not int for ident in ids) or len(set(ids)) != len(ids):
        raise AssertionError("Every metadata row must retain a unique original integer ID")
    return rows


def _expected_value(before, previous, expected):
    if isinstance(before, dict):
        if before.get("en_US") not in (previous, expected):
            raise AssertionError("Unexpected original source-language correction message")
        return dict(before, en_US=expected)
    if isinstance(before, str) and before in (previous, expected):
        return expected
    raise AssertionError("Unexpected original correction metadata shape or value")


def verify(original, current):
    """Return a three-field audit only after checking all original field rows.

Unchanged, already upgraded metadata is idempotent. Extra field rows are not
original history; this helper never licenses changes to other existing rows.
The caller must still verify the other identity-contract tables normally.
"""
    provenance = source_contract()
    original, current = _rows(original), _rows(current)
    now = {row["id"]: row for row in current}
    target_names = [row["name"] for row in original if row.get("model") == MODEL and row.get("name") in EXPECTED]
    if len(target_names) != 3 or set(target_names) != set(EXPECTED):
        raise AssertionError("The three original correction fields must exist exactly once")
    current_targets = [row["name"] for row in current if row.get("model") == MODEL and row.get("name") in EXPECTED]
    if len(current_targets) != 3 or set(current_targets) != set(EXPECTED):
        raise AssertionError("Correction metadata cannot add a second identity for an original field")
    audit = []
    for row in original:
        got = now.get(row["id"])
        if got is None:
            raise AssertionError("Original field ID removed: " + str(row["id"]))
        expected_row = deepcopy(row)
        name = row.get("name") if row.get("model") == MODEL else None
        if name in EXPECTED:
            for prop, message in EXPECTED[name].items():
                if prop not in row:
                    raise AssertionError("Missing original metadata property: " + name + "." + prop)
                expected_row[prop] = _expected_value(row[prop], PREVIOUS[name][prop], message)
            audit.append({"id": row["id"], "model": MODEL, "name": name,
                "properties": list(EXPECTED[name]),
                "before": {prop: row[prop] for prop in EXPECTED[name]},
                "after": {prop: got.get(prop) for prop in EXPECTED[name]},
                "other_properties_preserved": True})
        if got != expected_row:
            changed = sorted(set(got) ^ set(expected_row) | {key for key in got.keys() & expected_row.keys() if got[key] != expected_row[key]})
            raise AssertionError("Unexpected existing field metadata change: " + str(row["id"]) + " " + ",".join(changed))
    return {"model": MODEL, "fields": sorted(audit, key=lambda item: item["id"]),
            "original_field_count": len(original), "original_ids_preserved": True,
            "source": provenance}
