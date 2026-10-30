"""Pure custody negatives for the actual one-keyword OCA derivation."""
import unittest
import build_numeric_input_engine as builder


class NumericEngineCase(unittest.TestCase):
    def source(self):
        return {"__manifest__.py": b"{'license':'LGPL-3','data':['views.xml']}", "views.xml": b"<odoo/>",
            builder.FILE: b"from odoo import fields, models\nclass HrPayslipInput(models.Model):\n    amount = fields.Float(\n        help='Original text'\n    )\n    code = fields.Char(required=True)\n"}

    def test_only_supported_keyword_changes_and_all_other_bytes_stay(self):
        source = self.source(); result = builder.plan(source)
        self.assertEqual(set(source),set(result))
        self.assertEqual(result[builder.FILE].replace(builder.AFTER,builder.BEFORE,1),source[builder.FILE])
        self.assertEqual(result['views.xml'],source['views.xml'])
        self.assertNotIn(b'digits=',source[builder.FILE])

    def test_nonfree_manifest_missing_runtime_and_nonreal_field_are_rejected(self):
        for replacement in [b"{'license':'OEEL-1'}", b"{'license':'LGPL-3','data':['missing.xml']}"]:
            source=self.source();source['__manifest__.py']=replacement
            with self.assertRaises(ValueError):builder.plan(source)
        source=self.source();source[builder.FILE]=source[builder.FILE].replace(b'fields.Float(',b'fake.Float(')
        with self.assertRaises(ValueError):builder.plan(source)

    def test_existing_precision_default_or_duplicate_cannot_be_overridden(self):
        for change in [b'digits=(16,2), ',b'default=0, ',b'compute="fake", ']:
            source=self.source();source[builder.FILE]=source[builder.FILE].replace(b"help='Original",change+b"help='Original")
            with self.assertRaises(ValueError):builder.plan(source)
        source=self.source();source[builder.FILE]+=builder.BEFORE
        with self.assertRaises(ValueError):builder.plan(source)


if __name__=='__main__':unittest.main()
