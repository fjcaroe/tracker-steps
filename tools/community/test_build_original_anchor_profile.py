"""Safety boundary for the private original-policy runtime derivation."""
import ast
from pathlib import Path
import unittest

from build_original_anchor_profile import ui_profile
import derive_original_payroll_storage as derive


class OriginalPolicyProfileCase(unittest.TestCase):
    def profile(self, entries):
        spec = {'license': 'LGPL-3', 'data': list(entries)}
        return ui_profile(repr(spec).encode(), entries)

    def test_omits_seed_and_security_including_csv(self):
        raw, proof = self.profile({'security/access.csv': b'not XML',
            'security/groups.xml': b'<odoo/>', 'data/masters.xml': b'<odoo/>',
            'views/form.xml': b'<odoo><record id="form" model="ir.ui.view"/></odoo>'})
        self.assertEqual(proof['kept_ui'], ['views/form.xml'])
        self.assertEqual(len(proof['omitted_seed_and_policy']), 3)
        self.assertNotIn(b'access.csv', raw)

    def test_rejects_business_producer_disguised_as_view(self):
        with self.assertRaises(AssertionError):
            self.profile({'views/form.xml': b'<odoo><record model="hr.salary.rule"/></odoo>'})

    def test_rejects_function_and_delete_in_ui(self):
        for tag in ('function', 'delete'):
            with self.subTest(tag=tag), self.assertRaises(AssertionError):
                self.profile({'views/form.xml': ('<odoo><' + tag + '/></odoo>').encode()})

    def test_rejects_path_escape_and_unreviewed_format(self):
        for name in ('../views/form.xml', '/views/form.xml', 'views/access.csv'):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                self.profile({name: b'<odoo/>'})

    def test_requires_actual_community_ui(self):
        with self.assertRaises(AssertionError):
            self.profile({'data/masters.xml': b'<odoo/>'})

    def test_builder_storage_is_opt_in_after_properties_before_ui_with_no_database_api(self):
        source = (Path(derive.__file__).parent / 'build_original_anchor_profile.py').read_text(encoding='utf-8-sig')
        self.assertIn('original_storage=False, schema_plan=None', source)
        self.assertLess(source.index('property_derivation = apply_original_property_derivation'),
            source.index('storage_derivation = apply_anchor_storage_derivation'))
        self.assertLess(source.index('storage_derivation = apply_anchor_storage_derivation'), source.index('changes = {}'))
        tree = ast.parse(Path(derive.__file__).read_text(encoding='utf-8-sig'))
        methods = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(methods & {'connect', 'db_connect', 'execute', 'sudo', 'compute_sheet', 'commit'})
        self.assertIn('O_EXCL', Path(derive.__file__).read_text())


if __name__ == '__main__':
    unittest.main()
