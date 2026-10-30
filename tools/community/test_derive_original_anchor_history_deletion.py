"""Synthetic full-chain boundaries; no runtime, database or vendor fixture copy."""
import ast
from contextlib import ExitStack
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import derive_original_anchor_history_deletion as derive
import test_derive_original_anchor_company as company_fixture
import test_derive_original_anchor_properties as property_fixture
from test_derive_original_payroll_storage import provider, schema_plan
from test_derive_original_history_deletion import BODY
import test_build_numeric_input_engine as numeric_fixture


def fixture():
    files, capsule = company_fixture.OriginalCompanyDerivationCase().inputs()
    props, unused = property_fixture.OriginalPropertyDerivationCase().inputs()
    files["models/hr_salary_rule.py"] += b'    note = fields.Text(string="Description")\n'
    files["models/hr_payslip_line.py"] = props["payroll"]["models/hr_payslip_line.py"]
    files.update({name: raw for name, raw in provider().items() if name in
        ("models/hr_contract.py", "models/hr_payslip_worked_days.py")})
    files[derive.numeric.FILE] = numeric_fixture.NumericEngineCase().source()[derive.numeric.FILE]
    files[derive.deletion.FILE] = BODY
    for table, names in (("hr_salary_rule", ("account_debit", "account_credit", "analytic_account_id", "note")),
            ("hr_payroll_structure", ("journal_id",))):
        spec = capsule["tables"][table]
        rows = [dict(json.loads(raw), **{name: None for name in names}) for raw in spec["rows_json"]]
        spec["rows_json"] = [json.dumps(row) for row in rows]
        spec["rows_sha256"] = derive.contract.sha("\n".join(spec["rows_json"]).encode())
        spec["columns"] += [{"name": name, "pg_type": "jsonb", "not_null": False} for name in names]
    for number in range(144 - len(files)):
        files["synthetic/unmodified-%03d.txt" % number] = b"unit fixture only\n"
    root = Path(__file__).resolve().parents[2]
    guards = {name: (root / name).read_bytes() for name in derive.contract.GUARD_PATHS}
    return files, props["payroll_account"], json.dumps(schema_plan()).encode(), json.dumps(capsule).encode(), guards


def admitted(facts):
    files, accounting, schema, capsule, guards = facts
    stack = ExitStack()
    stack.enter_context(patch.object(derive.company, "FILE_SHA256", derive.contract.sha(files[derive.company.FILE])))
    stack.enter_context(patch.object(derive.company, "CAPSULE_SHA256", derive.contract.sha(capsule)))
    stack.enter_context(patch.object(derive.storage, "SCHEMA_PLAN_SHA256", derive.contract.sha(schema)))
    hashes = {(module, name): derive.contract.sha((files if module == "payroll" else accounting)[name])
        for module, name in derive.properties.PINNED_SOURCE}
    stack.enter_context(patch.object(derive.properties, "PINNED_SOURCE", hashes))
    modules, unused = derive.properties.plan({"payroll": files, "payroll_account": accounting}, json.loads(capsule))
    stack.enter_context(patch.object(derive.storage, "PINNED_SOURCE", {
        name: derive.contract.sha(files[name]) for name in derive.storage.PINNED_SOURCE}))
    stack.enter_context(patch.object(derive.storage, "ANCHOR_PROPERTY_LINE_SHA256",
        derive.contract.sha(modules["payroll"]["models/hr_payslip_line.py"])))
    stack.enter_context(patch.object(derive.deletion, "SOURCE_SHA256", derive.contract.sha(BODY)))
    return stack


class AnchorHistoryCompositionCase(unittest.TestCase):
    def test_all_five_stages_replay_144_files_and_only_final_relation_file_changes(self):
        facts = fixture(); original = dict(facts[0])
        self.assertEqual(derive.contract.GUARD_SHA256,
            derive.contract.sha(derive.contract.lf(facts[-1][derive.contract.GUARD_FILE])))
        with admitted(facts):
            before, final, accounting, report = derive.plan_anchor_history_deletion(*facts)
        self.assertEqual(original, facts[0])
        self.assertEqual([row["stage"] for row in report["stages"]], ["numeric-input", "original-global-company",
            "original-properties", "original-hr-storage", "original-company-run-deletion"])
        self.assertTrue(all(len(row["before_files"]) == len(row["after_files"]) == 144 for row in report["stages"]))
        self.assertEqual([name for name in before if before[name] != final[name]], [derive.deletion.FILE])
        derive.verify_anchor_inputs(before, accounting, before, accounting)
        self.assertTrue(report["anchored_properties_profile"])
        self.assertTrue(report["requires_pre_orm_company_null_admission"])
        self.assertFalse(report["database_accessed"])
        self.assertFalse(report["operational_acceptance"])

    def test_incomplete_chain_or_accounting_drift_cannot_be_called_the_anchored_input(self):
        facts = fixture()
        with admitted(facts):
            before, final, accounting, unused = derive.plan_anchor_history_deletion(*facts)
        for altered in (facts[0], final, dict(before, **{derive.numeric.FILE: b"wrong\n"})):
            with self.assertRaises(ValueError): derive.verify_anchor_inputs(altered, accounting, before, accounting)
        changed = dict(accounting); changed[next(iter(changed))] += b"\n# drift\n"
        with self.assertRaises(ValueError): derive.verify_anchor_inputs(before, changed, before, accounting)

    def test_real_imported_guard_is_checked_before_any_cascade_plan(self):
        facts = fixture()
        for mode in ("missing", "changed", "not-imported", "old-version"):
            altered = list(facts); guards = dict(altered[-1]); altered[-1] = guards
            if mode == "missing": guards.pop(derive.contract.GUARD_FILE)
            if mode == "changed": guards[derive.contract.GUARD_FILE] = b"guard_present=True\n"
            if mode == "not-imported": guards["step_payroll_oca_api/models/__init__.py"] = b"# no import\n"
            if mode == "old-version": guards["step_payroll_oca_api/__manifest__.py"] = b"{'version':'18.0.1.16.0','license':'LGPL-3'}"
            with admitted(facts), patch.object(derive.deletion, "plan_history_deletion") as invoked:
                with self.subTest(mode=mode), self.assertRaises(ValueError): derive.plan_anchor_history_deletion(*altered)
                invoked.assert_not_called()

    def test_capsule_and_schema_bytes_remain_sealed_inputs(self):
        facts = fixture()
        for index in (2, 3):
            altered = list(facts); altered[index] += b" "
            with admitted(facts), self.assertRaises(ValueError): derive.plan_anchor_history_deletion(*altered)

    def test_builder_calls_only_opted_in_anchor_after_hr_storage_before_ui(self):
        path = Path(__file__).with_name("build_original_anchor_profile.py")
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        calls = {node.func.id: node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertLess(calls["apply_anchor_storage_derivation"].lineno, calls["apply_anchor_history_deletion"].lineno)
        self.assertLess(calls["apply_anchor_history_deletion"].lineno, calls["ui_profile"].lineno)
        blocks = [node for node in ast.walk(tree) if isinstance(node, ast.If) and isinstance(node.test, ast.Name)
            and node.test.id == "original_storage"]
        self.assertTrue(any(any(call is calls["apply_anchor_history_deletion"] for call in ast.walk(block)) for block in blocks))


if __name__ == "__main__":
    unittest.main()
