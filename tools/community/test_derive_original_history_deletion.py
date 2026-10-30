"""Synthetic AST boundaries; real pinned source is verified by the builder."""
import ast
from copy import deepcopy
import unittest
from unittest.mock import patch

import derive_original_history_deletion as derivation


BODY = b'''class HrPayslip:
    company_id = fields.Many2one(
        "res.company",
        readonly=True,
        copy=False,
        default=lambda self: self.env.company,
    )
    payslip_run_id = fields.Many2one(
        "hr.payslip.run",
        readonly=True,
        copy=False,
        tracking=True,
    )
    def untouched(self):
        return "unchanged"
'''


def fixture(body=BODY, license="LGPL-3"):
    return {"__manifest__.py": repr({"license": license}).encode(),
        derivation.FILE: body, "models/untouched.py": b"# unchanged\n"}


class OriginalHistoryDerivationCase(unittest.TestCase):
    def test_two_supported_policies_preserve_all_other_files_defaults_and_methods(self):
        source = fixture()
        before = deepcopy(source)
        with patch.object(derivation, "SOURCE_SHA256", derivation.sha(BODY)):
            result, proof = derivation.plan_history_deletion(source)
        self.assertEqual(source, before)
        self.assertEqual({name for name in source if source[name] != result[name]}, {derivation.FILE})
        ast.parse(result[derivation.FILE])
        self.assertIn(b"required=True", result[derivation.FILE])
        self.assertIn(b"ondelete='restrict'", result[derivation.FILE])
        self.assertIn(b"ondelete='cascade'", result[derivation.FILE])
        self.assertIn(b"default=lambda self: self.env.company", result[derivation.FILE])
        self.assertTrue(proof["requires_actual_api_draft_deletion_guard"])
        self.assertFalse(proof["database_accessed"])
        self.assertFalse(proof["historical_rows_rewritten"])

    def test_unreviewed_hash_or_nonfree_source_is_not_derived(self):
        with self.assertRaisesRegex(ValueError, "source differs"):
            derivation.plan_history_deletion(fixture())
        with patch.object(derivation, "SOURCE_SHA256", derivation.sha(BODY)), self.assertRaisesRegex(ValueError, "LGPL"):
            derivation.plan_history_deletion(fixture(license="OEEL-1"))

    def test_changed_relation_duplicate_or_existing_policy_still_fails_after_explicit_synthetic_hash(self):
        changed = (BODY.replace(b'"res.company"', b'"res.partner"'),
            BODY.replace(b"readonly=True", b"required=False,\n        readonly=True", 1),
            BODY.replace(b"tracking=True", b"ondelete='set null',\n        tracking=True"),
            BODY + b"    company_id = fields.Many2one('res.company')\n",
            BODY.replace(b"fields.Many2one", b"fields.Char", 1))
        for body in changed:
            with self.subTest(body=derivation.sha(body)), patch.object(derivation, "SOURCE_SHA256", derivation.sha(body)), self.assertRaises(ValueError):
                derivation.plan_history_deletion(fixture(body))


if __name__ == "__main__":
    unittest.main()
