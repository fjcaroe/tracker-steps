"""Dump reconstruction boundaries; no database, float or private row fixtures."""
from pathlib import Path, PurePosixPath
import tempfile
import unittest

import audit_stock_package_representation as audit


class DumpReconstructionCase(unittest.TestCase):
    def test_original_bootstrap_or_contracts_private_roots_remain_admitted(self):
        for name in ('community-original-bootstrap-20261029F', 'community-original-contracts-20261030B'):
            self.assertTrue(audit.native_root_allowed(PurePosixPath('/opt/steps-validation') / name))
        for value in ('/opt/steps-validation/community-sys-20261030B', '/var/lib/postgresql/community-original-contracts-20261030B',
                      'community-original-contracts-20261030B', '/opt/steps-validation/../community-original-contracts-20261030B',
                      '/opt/steps-validation/community-original-contracts-20261030B/other'):
            with self.subTest(value=value):
                self.assertFalse(audit.native_root_allowed(PurePosixPath(value)))

    def test_multifront_prefix_requires_private_parent_and_exact_prefix(self):
        self.assertTrue(audit.native_root_allowed(PurePosixPath('/opt/steps-validation/community-multifront-20261030A')))
        for value in ('/opt/steps-validation-other/community-multifront-20261030A',
                      '/opt/steps-validation/community-multifront',
                      '/opt/steps-validation/other-community-multifront-20261030A',
                      '/opt/steps-validation/../community-multifront-20261030A',
                      'community-multifront-20261030A'):
            with self.subTest(value=value):
                self.assertFalse(audit.native_root_allowed(PurePosixPath(value)))

    def test_original_and_full_multifront_acceptance_are_disjoint_and_exact(self):
        original_root = PurePosixPath('/opt/steps-validation/community-original-contracts-20261030C')
        multifront_root = PurePosixPath('/opt/steps-validation/community-multifront-20261030A')
        original = {'mode': 'cerro-reference', 'writes_to_source': False,
            'expected_test_count': 294, 'counts': {'installed': 391, 'enterprise': 140}}
        #393 is a synthetic test pin, not an observation of a real environment.
        multifront = dict(original, expected_test_count=391, multifront=True, focused=False,
                          counts={'installed': 393, 'enterprise': 140})
        audit.validate_native_acceptance(original_root, original)
        audit.validate_native_acceptance(multifront_root, multifront, expected_multifront_installed=393)
        for root, value, pin in ((multifront_root, original, 391), (original_root, multifront, None),
                                (multifront_root, multifront, None), (multifront_root, multifront, 394),
                                (multifront_root, multifront, True), (original_root, original, 391)):
            with self.subTest(root=str(root), pin=pin), self.assertRaises(ValueError):
                audit.validate_native_acceptance(root, value, expected_multifront_installed=pin)
        for patch in ({'mode': 'community'}, {'multifront': False}, {'focused': True},
                      {'focused': None}, {'expected_test_count': 294}, {'expected_test_count': 392},
                      {'writes_to_source': True}, {'counts': {'installed': 393, 'enterprise': 139}}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                audit.validate_native_acceptance(multifront_root, dict(multifront, **patch), expected_multifront_installed=393)
        for patch in ({'expected_test_count': 391}, {'counts': {'installed': 392, 'enterprise': 140}},
                      {'multifront': True}, {'focused': True}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                audit.validate_native_acceptance(original_root, dict(original, **patch))

    def schema(self):
        columns = ',\n'.join('    ' + name + ' ' + kind + (' NOT NULL' if required else '')
            for name, kind, required in audit.COLUMNS)
        return 'CREATE TABLE public.stock_package_type (\n' + columns + '\n);\n'

    def data(self):
        rows = []
        for ident in range(1, 6):
            values = [str(ident), '10', r'\N', '1', '1', 'Package '+str(ident), r'\N',
                '2026-10-29 12:00:00.000001', '2026-10-29 12:00:00', '0', '0', '0',
                '0.000000', '0', '0.00', '0.0', '0', r'\N', '0.000']
            rows.append('\t'.join(values))
        return 'COPY public.stock_package_type (' + ', '.join(column[0] for column in audit.COLUMNS) + ') FROM stdin;\n' + '\n'.join(rows) + '\n\\.\n'

    def test_exact_schema_rejects_defaults_types_names_and_other_objects(self):
        self.assertEqual(tuple(audit.schema_columns(self.schema())), audit.COLUMNS)
        for old, new in (('base_weight numeric', 'base_weight real'), ('id integer NOT NULL', 'id integer'),
                         ('name character varying', 'label character varying'),
                         ('sequence integer', 'sequence integer DEFAULT nextval(\'private\')'),
                         ('public.stock_package_type', 'public.other_table')):
            with self.subTest(new=new), self.assertRaises(ValueError):
                audit.schema_columns(self.schema().replace(old, new))
        with self.assertRaises(ValueError): audit.schema_columns(self.schema() * 2)

    def test_copy_null_escaping_unicode_and_numeric_scale_never_use_float(self):
        rows = audit.copy_rows(self.data())
        self.assertEqual(rows[0][2], None)
        self.assertEqual(rows[0][12], '0.000000')
        self.assertTrue(all(value is None or type(value) is str for row in rows for value in row))
        self.assertEqual(audit.copy_value(r'\N'), None)
        self.assertEqual(audit.copy_value(r'\\N'), r'\N')
        self.assertEqual(audit.copy_value(r'caf\303\251\t\x41\n\\'), 'café\tA\n\\')
        for value in ('bad\\', r'\q', r'\x', r'\777', r'\000', r'\377'):
            with self.subTest(value=value), self.assertRaises(ValueError): audit.copy_value(value)

    def test_copy_count_identity_order_finite_and_timestamp_boundaries(self):
        data = self.data()
        for changed in (data.replace('id, sequence', 'sequence, id'), data * 2,
                        data.replace('0.000000', 'NaN'), data.replace('2026-10-29 12:00:00', 'infinity'),
                        data.replace('\n5\t', '\n1\t'), data.replace('COPY public.stock_package_type', 'COPY public.other')):
            with self.subTest(changed=changed[:40]), self.assertRaises(ValueError): audit.copy_rows(changed)
        start, *rows, end = data.splitlines()
        with self.assertRaises(ValueError): audit.copy_rows('\n'.join([start, *rows[:-1], end])+'\n')

    def test_values_are_hex_encoded_and_only_reviewed_types_become_sql(self):
        rows = audit.copy_rows(self.data())
        raw = "'); DELETE FROM stock_package_type; --\n\\"
        rows[0][5] = raw
        query = audit.typed_values(rows)
        self.assertTrue(query.startswith('WITH t ("id",'))
        self.assertIn(raw.encode().hex(), query)
        self.assertNotIn(raw, query)
        self.assertNotIn('DELETE', query)
        self.assertIn('NULL::integer', query)
        self.assertIn('::double precision', query)
        with self.assertRaises(ValueError): audit.typed_values(rows[:1])

    def test_only_exact_versioned_normalizer_is_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'normalizer.py'
            path.write_text('def snapshot(database):\n normalized = '+repr(audit.NORMALIZER)+'\n')
            self.assertEqual(audit.normalizer(path), audit.NORMALIZER)
            path.write_text('def snapshot(database):\n normalized = '+repr(audit.NORMALIZER.replace('jsonb_each', 'unsafe_function'))+'\n')
            with self.assertRaises(ValueError): audit.normalizer(path)


if __name__ == '__main__':
    unittest.main()
