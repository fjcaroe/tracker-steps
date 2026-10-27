import unittest
from packing_material_hierarchy_setup import capture, snapshot_row


class MaterialHierarchyGuardCase(unittest.TestCase):
    def plan(self, rows, descendant_count='0'):
        import json
        def query(database, statement):
            return descendant_count if 'count(*)' in statement else json.dumps(rows)
        return capture(query, 'private', 'cerro')

    def test_only_approved_children_allow_expected_structure_changes(self):
        row = snapshot_row('to_jsonb(t)', {'children': [19, 20]})
        self.assertIn('t.id IN (19,20)', row)
        self.assertIn('parent_id', row)
        self.assertIn('complete_name', row)
        self.assertNotIn("'name'", row)
        self.assertNotIn('property_account', row)

    def test_refuses_ambiguous_root_foreign_parent_or_new_descendants(self):
        rows = [{'id': 8, 'name': '6 materiales de embalajes'},
                {'id': 19, 'name': '6.1 materiales de caja', 'parent_id': None},
                {'id': 20, 'name': '6.2 materiales de pallet', 'parent_id': None}]
        self.assertEqual(self.plan(rows)['children'], [19, 20])
        for candidate, descendants in (
            (rows + [{'id': 30, 'name': '6 materiales de embalaje'}], '0'),
            ([rows[0], dict(rows[1], parent_id=99), rows[2]], '0'),
            (rows, '1'),
        ):
            with self.assertRaises(AssertionError):
                self.plan(candidate, descendants)


if __name__ == '__main__':
    unittest.main()
