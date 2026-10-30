"""Pure observer/projection contract tests, never a native visibility oracle."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import probe_original_master_visibility as probe


class Denied(Exception):
    pass


class MasterObserverFixture:
    def __init__(self, ids, *, extra=False, inconsistent=False):
        self.env = SimpleNamespace(su=False)
        self.ids = ids; self.fields = []; self.extra = extra; self.inconsistent = inconsistent

    def search(self, domain, order):
        assert order == 'id' and domain[0][0:2] == ('id', 'in')
        return SimpleNamespace(ids=[*sorted(self.ids), 99] if self.inconsistent else sorted(self.ids))

    def browse(self, ident):
        outer = self
        class Row:
            def read(self, fields):
                outer.fields.append(fields)
                if ident not in outer.ids: raise Denied()
                return [{'id': ident, 'name': 'unexpected'}] if outer.extra else [{'id': ident}]
        return Row()


class NativeMasterVisibilityContractCase(unittest.TestCase):
    def test_normal_id_only_read_derives_allowed_and_denied_without_country_heuristics(self):
        model = MasterObserverFixture({1, 3})
        result = probe.observe_model(model, [1, 2, 3, 4], access_error=Denied)
        self.assertEqual(result['allowed_ids'], [1, 3])
        self.assertEqual(result['denied_ids'], [2, 4])
        self.assertEqual(result['search_ids'], [1, 3])
        self.assertTrue(result['search_and_per_record_read_agree'])
        self.assertEqual(model.fields, [['id']]*4)
        self.assertFalse(result['superuser'])

    def test_sudo_extra_fields_or_search_read_disagreement_abort(self):
        for change in ('sudo', 'extra', 'disagree'):
            model = MasterObserverFixture({1}, extra=change == 'extra', inconsistent=change == 'disagree')
            if change == 'sudo': model.env.su = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                probe.observe_model(model, [1, 2], access_error=Denied)

    def test_only_fixed_nonfinancial_projection_columns_and_original120_are_admitted(self):
        capsule = {'tables': {}}
        for index, (table, (model, fields)) in enumerate(probe.SPECS.items()):
            rows = [{key: ident if key == 'id' else None for key in fields} for ident in range(index*24+1, index*24+25)]
            capsule['tables'][table] = {'model': model, 'row_count': 24, 'rows_json': [json.dumps(row) for row in rows]}
        result = probe.expected_projection(capsule)
        self.assertEqual(sum(len(rows) for rows in result.values()), 120)
        for table, (model, fields) in probe.SPECS.items():
            self.assertEqual(set(result[table][0]), set(fields))
            self.assertFalse(set(fields) & {'name','amount','wage','amount_python_compute','total'})
        capsule['tables'][next(iter(probe.SPECS))]['rows_json'].pop()
        with self.assertRaises(ValueError): probe.expected_projection(capsule)
        with self.assertRaises(ValueError): probe.identifier('unsafe; DELETE')

    def test_runtime_boundary_uses_actual_readonly_connection_and_original_native_registry(self):
        source = Path(probe.__file__).read_text(encoding='utf-8-sig')
        tree = ast.parse(source)
        runtime = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
        methods = {node.func.attr for node in ast.walk(runtime) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertNotIn('create', methods)
        writes = [node for node in ast.walk(runtime) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'write']
        self.assertTrue(all(isinstance(node.func.value, ast.Name) and node.func.value.id == 'stream' for node in writes))
        self.assertNotIn('sudo', methods); self.assertNotIn('compute_sheet', methods)
        self.assertIn('db_connect(database, readonly=True).cursor()', source)
        self.assertIn('cr.readonly is True', source)
        self.assertIn("'repeatable read'", source)
        self.assertIn('untouched-source381-native140-required', source)
        self.assertIn('fresh-private-original-native-control-required', source)


if __name__ == '__main__':
    unittest.main()
