"""Transaction-control boundaries only; never starts Odoo or a database."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import original_handover_savepoint as core
import probe_original_handover as probe


NAME = '11111111-2222-1333-8444-555555555555'  # synthetic UUID1


class SavepointGuardCase(unittest.TestCase):
    def test_only_canonical_core_uuid1_control_shapes_match(self):
        for operation in core.METHODS:
            self.assertEqual(core.control(operation + ' "' + NAME + '"'), (operation, NAME))
        for code in (
            'SAVEPOINT "arbitrary-hyphen"', 'SAVEPOINT "' + NAME.upper() + 'A"',
            'SAVEPOINT "' + NAME.replace('-1333-', '-4333-') + '"',
            'SAVEPOINT "' + NAME.replace('-8444-', '-7444-') + '"',
            'SAVEPOINT "' + NAME + '"; COMMIT', 'COMMIT', 'ROLLBACK',
            'SELECT "' + NAME + '" FROM hr_salary_rule', 'SAVEPOINT "a""b"',
            'SAVEPOINT "' + NAME + '" SELECT nextval(%s)', ' SAVEPOINT "' + NAME + '"',
        ):
            with self.subTest(code=code): self.assertIsNone(core.control(code))
        # Hyphenated identifiers were not added to the generic SQL lexer.
        with self.assertRaises(probe.ProbeBlocked): probe.admit_sql('SAVEPOINT "' + NAME + '"')

    def test_real_core_origin_and_projection_phase_are_required_before_delegation(self):
        class Cursor:
            def __init__(self): self.calls = []
            def execute(self, code, *args, **kwargs):
                self.calls.append((code, args, kwargs)); return 'unchanged-real-result'
        cursor = Cursor(); code = 'SAVEPOINT "' + NAME + '"'
        with self.assertRaisesRegex(probe.ProbeBlocked, 'outside-original-projection'):
            with probe.observe_cursor(cursor): cursor.execute(code)
        with self.assertRaises(core.SavepointBlocked):
            with probe.observe_cursor(cursor) as observation:
                observation['projection'] = True; cursor.execute(code)
        self.assertEqual(cursor.calls, [])
        proof = {'actual-core-binding': 'synthetic-boundary-fixture'}
        with patch.object(core, 'current_origin', return_value=proof):
            with probe.observe_cursor(cursor) as observation:
                observation['projection'] = True
                for operation in core.METHODS:
                    self.assertEqual(cursor.execute(operation + ' "' + NAME + '"'), 'unchanged-real-result')
                self.assertEqual(observation['pinned_core_savepoints'], {'controls': {
                    name: 1 for name in core.METHODS}, 'contract': proof})
        self.assertEqual(len(cursor.calls), 3)

    def test_official_method_object_name_cursor_and_open_state_cannot_be_forged_by_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'odoo', 'sql_db.py'); path.parent.mkdir()
            text = '''class Savepoint:
    def __init__(self, cr):
        self.name = NAME if CHANGE != 'name' else 'different'
        self._cr = cr if CHANGE != 'cursor' else object()
        self.closed = CHANGE == 'closed'
        self.proof = verify('SAVEPOINT', NAME, cr)
'''
            path.write_text(text)
            for change in ('none', 'name', 'cursor', 'closed'):
                namespace = {'__name__': 'odoo.sql_db', 'NAME': NAME, 'CHANGE': change, 'verify': core.current_origin}
                exec(compile(text, str(path), 'exec'), namespace)
                with patch.object(core, 'inspect_source', return_value={'actual-file-and-ast': 'fixture'}):
                    if change == 'none':
                        value = namespace['Savepoint'](object())
                        self.assertTrue(value.proof['same_cursor'])
                        self.assertTrue(value.proof['same_generated_uuid1'])
                        self.assertFalse(value.proof['generic_quoted_identifiers_admitted'])
                    else:
                        with self.subTest(change=change), self.assertRaises(core.SavepointBlocked):
                            namespace['Savepoint'](object())
            # Real file-byte/AST inspection still rejects this synthetic file.
            with self.assertRaises(core.SavepointBlocked):
                core.inspect_source(str(path), (1, 2, 3, 4))


if __name__ == '__main__':
    unittest.main()
