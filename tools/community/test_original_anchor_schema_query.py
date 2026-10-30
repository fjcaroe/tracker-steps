"""Catalog-query boundary regression; real PG execution is a private receipt."""
import ast
import json
from pathlib import Path
import unittest

from original_anchor_readonly_sql import admit_statement


class PhysicalSchemaQueryCase(unittest.TestCase):
    def test_constraint_name_is_a_quoted_label_and_column_contract_is_preserved(self):
        tree = ast.parse(Path(__file__).with_name('review_original_anchor.py').read_text(encoding='utf-8'))
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'physical_schema')
        calls = []
        expected = {'columns': [{'table_name': 'original_table', 'column_name': 'original_id',
            'sql_type': 'integer', 'not_null': True, 'default_md5': None}],
            'constraints': [{'table_name': 'original_table', 'name': 'original_table_pkey',
                'kind': 'p', 'valid': True, 'definition_md5': 'a' * 32}]}
        class Gate:
            @staticmethod
            def literal(value):
                return "'" + value.replace("'", "''") + "'"
        def sql(database, query):
            admit_statement(query)
            calls.append((database, query))
            return json.dumps(expected)
        namespace = {'gate': Gate, 'json': json, 'sql': sql}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual-catalog-builder>', 'exec'), namespace)
        result = namespace['physical_schema']('private', ['original_table'])
        self.assertEqual(result, expected)
        self.assertEqual(len(calls), 1)
        self.assertIn('k.conname AS "name"', calls[0][1])
        self.assertIn('ORDER BY table_name,"name"', calls[0][1])
        self.assertNotIn('k.conname name,', calls[0][1])


if __name__ == '__main__':
    unittest.main()
