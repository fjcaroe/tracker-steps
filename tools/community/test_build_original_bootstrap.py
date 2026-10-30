"""Pure synthetic reference-graph and byte-custody tests; no client data."""
import unittest
from unittest.mock import patch
import os
from pathlib import Path
import tempfile

import build_original_bootstrap as builder


def fixture(extra_xml="", python=""):
    data = list(builder.OMIT) + [builder.DEFER_FILE, "views/real.xml", "security/ir.model.access.csv"]
    return {
        "__manifest__.py": repr({"name": "Synthetic real provider", "license": "AGPL-3",
            "depends": ["step_simpledigital_oca_base"], "data": data}).encode(),
        "__init__.py": b"from . import models\n",
        "models/__init__.py": b"from . import real\n",
        "models/real.py": ("from odoo import models\nclass Real(models.Model):\n _name='synthetic.actual'\n" + python).encode(),
        builder.OMIT[0]: b"<odoo><record id='structure_chile' model='hr.payroll.structure'/></odoo>",
        builder.OMIT[1]: b"<odoo><record id='original_rule' model='hr.salary.rule'/></odoo>",
        builder.OMIT[2]: b"<odoo><record id='movement_type' model='hr.employee.movement.type'/><record id='movement_event' model='hr.employee.hr.event.type'/></odoo>",
        builder.DEFER_FILE: ("<odoo><record id='work_entry_type_unpaid_cl' model='hr.work.entry.type'>"
            "<field name='name'>Synthetic real unpaid type</field>"
            "<field name='unpaid_structure_ids' eval=\"[(4, ref('l10n_cl_simpledigital_payroll.structure_chile'))]\"/>"
            "</record></odoo>").encode(),
        "views/real.xml": ("<odoo><record id='real_form' model='ir.ui.view'><field name='inherit_id' ref='base.real_view'/></record>"
            "<template id='real_report'><t t-call='web.html_container'/></template>" + extra_xml + "</odoo>").encode(),
        "security/ir.model.access.csv": b"id,name,model_id:id,group_id:id,perm_read\naccess_actual,Actual,model_synthetic_actual,base.group_user,1\n",
    }


EXTERNAL = {"base.real_view": "ir.ui.view", "web.html_container": "ir.ui.view", "base.group_user": "res.groups"}


class OriginalBootstrapBuilderCase(unittest.TestCase):
    def test_receipt_is_exclusive_and_private_at_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            with patch.object(builder.os, "open", wraps=os.open) as opened:
                builder._write_receipt(path, {"synthetic": True})
            opened.assert_called_once_with(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                builder._write_receipt(path, {"replacement": True})
            self.assertEqual(path.read_bytes(), before)

    def test_omits_only_three_seed_files_and_keeps_runtime_views_acl_bytes(self):
        original = fixture()
        result, closure = builder.plan_profile(original, EXTERNAL)
        self.assertEqual(set(original) - set(result), set(builder.OMIT))
        self.assertEqual([name for name in result if result[name] != original[name]], ["__manifest__.py", builder.DEFER_FILE])
        fragment = closure["deferred_seed_assignment"]["fragment"].encode()
        self.assertEqual(result[builder.DEFER_FILE], original[builder.DEFER_FILE].replace(fragment, b""))
        self.assertFalse(closure["deferred_seed_assignment"]["adopted"])
        self.assertEqual(closure["retained_salary_records"], [])
        self.assertFalse(closure["original_aliases_guaranteed"])
        self.assertEqual(len(closure["omitted_definitions"]), 4)
        self.assertEqual(len(closure["deferred_movement_catalogue"]["records"]), 2)
        self.assertFalse(closure["deferred_movement_catalogue"]["generated_rules_adopted"])

    def test_required_reference_to_omitted_original_aborts_even_if_external_claims_it(self):
        original = fixture("<record id='bad' model='ir.ui.view'><field name='inherit_id' ref='structure_chile'/></record>")
        with self.assertRaisesRegex(builder.BootstrapError, "orphan-reference"):
            builder.plan_profile(original, dict(EXTERNAL, **{builder.MODULE + ".structure_chile": "hr.payroll.structure"}))

    def test_only_exact_unpaid_assignment_is_deferred_and_other_orphans_abort(self):
        for changed in (b"[(4, ref('other.structure'))]", b"[(6, 0, [ref('l10n_cl_simpledigital_payroll.structure_chile')])]",
                b"[(4, ref('l10n_cl_simpledigital_payroll.structure_chile')), (4, ref('other.structure'))]"):
            original = fixture()
            original[builder.DEFER_FILE] = original[builder.DEFER_FILE].replace(
                b"[(4, ref('l10n_cl_simpledigital_payroll.structure_chile'))]", changed)
            with self.assertRaisesRegex(builder.BootstrapError, "unpaid-seed-expression-drift"):
                builder.plan_profile(original, EXTERNAL)
        original = fixture("<record id='other' model='ir.ui.view'><field name='inherit_id' ref='original_rule'/></record>")
        with self.assertRaisesRegex(builder.BootstrapError, "orphan-reference"):
            builder.plan_profile(original, EXTERNAL)

    def test_optional_python_missing_seed_requires_explicit_false_contract(self):
        original = fixture(python=" def lookup(self):\n  return self.env.ref('l10n_cl_simpledigital_payroll.structure_chile', raise_if_not_found=False)\n")
        result, closure = builder.plan_profile(original, EXTERNAL)
        self.assertEqual(len(closure["optional_missing_seed_references"]), 1)
        self.assertEqual(result["models/real.py"], original["models/real.py"])
        original["models/real.py"] = original["models/real.py"].replace(b", raise_if_not_found=False", b"")
        with self.assertRaisesRegex(builder.BootstrapError, "orphan-reference"):
            builder.plan_profile(original, EXTERNAL)

    def test_dynamic_python_reference_aborts_instead_of_assuming_original_binding(self):
        original = fixture(python=" def lookup(self, name):\n  return self.env.ref(name, raise_if_not_found=False)\n")
        with self.assertRaisesRegex(builder.BootstrapError, "dynamic-xmlid-reference"):
            builder.plan_profile(original, EXTERNAL)

    def test_csv_and_eval_and_template_references_require_real_providers(self):
        for extra in ("<record id='bad' model='ir.ui.view'><field name='groups_id' eval=\"[(4, ref('base.missing'))]\"/></record>",
                "<template id='bad_report'><t t-call='base.missing'/></template>",
                "<menuitem id='bad_menu' action='%(base.missing)d'/>"):
            with self.assertRaisesRegex(builder.BootstrapError, "orphan-reference"):
                builder.plan_profile(fixture(extra), EXTERNAL)
        original = fixture()
        original["security/ir.model.access.csv"] = original["security/ir.model.access.csv"].replace(b"base.group_user", b"base.missing")
        with self.assertRaisesRegex(builder.BootstrapError, "orphan-reference"):
            builder.plan_profile(original, EXTERNAL)

    def test_retained_salary_seed_and_provider_demo_are_rejected(self):
        with self.assertRaisesRegex(builder.BootstrapError, "retained-salary-seed-record"):
            builder.plan_profile(fixture("<record id='unexpected' model='hr.salary.rule'/>"), EXTERNAL)
        original = fixture()
        spec = builder.manifest(original)
        original["demo.xml"] = b"<odoo/>"
        original["__manifest__.py"] = repr(dict(spec, demo=["demo.xml"])).encode()
        with self.assertRaisesRegex(builder.BootstrapError, "provider-demo-not-authorized"):
            builder.plan_profile(original, EXTERNAL)

    def test_any_other_retained_dynamic_salary_producer_or_movement_orphan_aborts(self):
        original = fixture("<record id='unexpected_movement' model='hr.employee.movement.type'/>")
        original["models/real.py"] += ("\nclass Movement(models.Model):\n _name='hr.employee.movement.type'\n"
            " def create(self, values):\n  return self.env['hr.salary.rule'].create(values)\n").encode()
        with self.assertRaisesRegex(builder.BootstrapError, "retained-dynamic-salary-producer"):
            builder.plan_profile(original, EXTERNAL)
        with self.assertRaisesRegex(builder.BootstrapError, "orphan-reference"):
            builder.plan_profile(fixture("<record id='unexpected_view' model='ir.ui.view'><field name='inherit_id' ref='movement_type'/></record>"), EXTERNAL)

    def test_snapshot_verifier_rejects_modified_runtime_source_and_receipt(self):
        normal = fixture()
        profile, closure = builder.plan_profile(normal, EXTERNAL)
        source = {"trusted.py": b"# synthetic exact source\n"}
        report = {"schema": 1, "profile": "original-bootstrap-without-salary-seeds", "license": "AGPL-3",
            "database_accessed": False, "engine_converted": False, "financial_certified": False,
            "community_pin": builder.PIN_COMMUNITY, "oca_pin": builder.PIN_OCA,
            "source_files": builder.hashes(source), "normal_files": builder.hashes(normal),
            "profile_files": builder.hashes(profile), "closure": closure}
        report["seal_sha256"] = builder.digest(report)
        pin = {"files": builder.hashes(source)}
        self.assertTrue(builder.verify_snapshots(source, normal, profile, report, EXTERNAL, pin))
        changed = dict(profile, **{"models/real.py": b"# unauthorized replacement\n"})
        with self.assertRaisesRegex(builder.BootstrapError, "profile-file-drift"):
            builder.verify_snapshots(source, normal, changed, report, EXTERNAL, pin)
        with self.assertRaisesRegex(builder.BootstrapError, "source-pin-drift"):
            builder.verify_snapshots({"trusted.py": b"changed"}, normal, profile, report, EXTERNAL, pin)
        report["financial_certified"] = True
        report["seal_sha256"] = builder.digest({key: value for key, value in report.items() if key != "seal_sha256"})
        with self.assertRaisesRegex(builder.BootstrapError, "report-cannot-certify-adoption"):
            builder.verify_snapshots(source, normal, profile, report, EXTERNAL, pin)

    def test_unimported_python_cannot_supply_generated_model_alias(self):
        original = fixture()
        original["models/unimported.py"] = b"from odoo import models\nclass Missing(models.Model):\n _name='synthetic.not_loaded'\n"
        original["security/ir.model.access.csv"] = original["security/ir.model.access.csv"].replace(b"model_synthetic_actual", b"model_synthetic_not_loaded")
        with self.assertRaisesRegex(builder.BootstrapError, "orphan-reference"):
            builder.plan_profile(original, EXTERNAL)


if __name__ == "__main__":
    unittest.main()
