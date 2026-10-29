"""Pure synthetic reference-graph and byte-custody tests; no client data."""
import unittest

import build_original_bootstrap as builder


def fixture(extra_xml="", python=""):
    data = list(builder.OMIT) + ["views/real.xml", "security/ir.model.access.csv"]
    return {
        "__manifest__.py": repr({"name": "Synthetic real provider", "license": "AGPL-3",
            "depends": ["step_simpledigital_oca_base"], "data": data}).encode(),
        "__init__.py": b"from . import models\n",
        "models/__init__.py": b"from . import real\n",
        "models/real.py": ("from odoo import models\nclass Real(models.Model):\n _name='synthetic.actual'\n" + python).encode(),
        builder.OMIT[0]: b"<odoo><record id='original_structure' model='hr.payroll.structure'/></odoo>",
        builder.OMIT[1]: b"<odoo><record id='original_rule' model='hr.salary.rule'/></odoo>",
        "views/real.xml": ("<odoo><record id='real_form' model='ir.ui.view'><field name='inherit_id' ref='base.real_view'/></record>"
            "<template id='real_report'><t t-call='web.html_container'/></template>" + extra_xml + "</odoo>").encode(),
        "security/ir.model.access.csv": b"id,name,model_id:id,group_id:id,perm_read\naccess_actual,Actual,model_synthetic_actual,base.group_user,1\n",
    }


EXTERNAL = {"base.real_view": "ir.ui.view", "web.html_container": "ir.ui.view", "base.group_user": "res.groups"}


class OriginalBootstrapBuilderCase(unittest.TestCase):
    def test_omits_only_two_seed_files_and_keeps_runtime_views_acl_bytes(self):
        original = fixture()
        result, closure = builder.plan_profile(original, EXTERNAL)
        self.assertEqual(set(original) - set(result), set(builder.OMIT))
        self.assertEqual([name for name in result if result[name] != original[name]], ["__manifest__.py"])
        self.assertEqual(closure["retained_salary_records"], [])
        self.assertFalse(closure["original_aliases_guaranteed"])
        self.assertEqual(len(closure["omitted_definitions"]), 2)

    def test_required_reference_to_omitted_original_aborts_even_if_external_claims_it(self):
        original = fixture("<record id='bad' model='ir.ui.view'><field name='inherit_id' ref='original_structure'/></record>")
        with self.assertRaisesRegex(builder.BootstrapError, "orphan-reference"):
            builder.plan_profile(original, dict(EXTERNAL, **{builder.MODULE + ".original_structure": "hr.payroll.structure"}))

    def test_optional_python_missing_seed_requires_explicit_false_contract(self):
        original = fixture(python=" def lookup(self):\n  return self.env.ref('l10n_cl_simpledigital_payroll.original_structure', raise_if_not_found=False)\n")
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

    def test_snapshot_verifier_rejects_modified_runtime_source_and_receipt(self):
        normal = fixture()
        profile, closure = builder.plan_profile(normal, EXTERNAL)
        source = {"trusted.py": b"# synthetic exact source\n"}
        report = {"source_files": builder.hashes(source), "normal_files": builder.hashes(normal),
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
        with self.assertRaisesRegex(builder.BootstrapError, "report-seal-drift"):
            builder.verify_snapshots(source, normal, profile, report, EXTERNAL, pin)

    def test_unimported_python_cannot_supply_generated_model_alias(self):
        original = fixture()
        original["models/unimported.py"] = b"from odoo import models\nclass Missing(models.Model):\n _name='synthetic.not_loaded'\n"
        original["security/ir.model.access.csv"] = original["security/ir.model.access.csv"].replace(b"model_synthetic_actual", b"model_synthetic_not_loaded")
        with self.assertRaisesRegex(builder.BootstrapError, "orphan-reference"):
            builder.plan_profile(original, EXTERNAL)


if __name__ == "__main__":
    unittest.main()
