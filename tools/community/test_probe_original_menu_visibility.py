"""Pure custody/observer tests; none constitutes a native menu oracle."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest

import probe_original_menu_visibility as probe


class AccessDenied(Exception):
    pass


def original_identity():
    aliases, menus = [], []
    for index, (key, menu, action, model) in enumerate(probe.ROUTES, 1):
        for alias, kind, ident in ((menu, 'ir.ui.menu', index), (action, 'ir.actions.act_window', index + 100)):
            module, name = alias.split('.', 1)
            aliases.append({'id': len(aliases) + 200, 'module': module, 'name': name,
                'model': kind, 'res_id': ident, 'noupdate': False})
        menus.append({'id': index, 'parent_id': None, 'action': 'ir.actions.act_window,' + str(index + 100), 'active': True})
    return {'original_xmlids': aliases, 'ir_ui_menu': menus, 'ir_ui_menu_group_rel': []}


class MenuObserverFixture:
    def __init__(self):
        self.debug_values = []; self.fields = []

    def _visible_menu_ids(self, debug=False):
        self.debug_values.append(debug)
        return {1, 2, 4}

    def browse(self, ident):
        outer = self
        class Row:
            def read(self, fields):
                outer.fields.append(fields)
                # Menu id readability and menu visibility are separate facts.
                return [{'id': ident}]
        return Row()


class ActorFixture:
    su = False

    def __init__(self):
        self.menus = MenuObserverFixture(); self.action_models = []

    def __getitem__(self, model):
        if model == 'ir.ui.menu':
            return self.menus
        assert model == 'ir.model.access'
        def check(model, operation, raise_exception):
            assert operation == 'read' and raise_exception is False
            self.action_models.append(model)
            return True
        return SimpleNamespace(check=check)


class NativeMenuVisibilityContractCase(unittest.TestCase):
    def test_exact_native_alias_and_action_binding_never_uses_display_names(self):
        identity = original_identity()
        resolved = probe.original_bindings(identity)
        self.assertEqual(set(resolved), {'structure', 'rule', 'category', 'input_type'})
        self.assertEqual(resolved['category']['menu_alias'], 'hr_payroll.menu_hr_salary_rule_category')
        self.assertEqual(resolved['category']['action_alias'], 'hr_payroll.action_hr_salary_rule_category')
        self.assertEqual(resolved['category']['model'], 'hr.salary.rule.category')
        self.assertTrue(all('name' not in row['menu'] for row in resolved.values()))

    def test_missing_duplicate_retargeted_alias_or_action_blocks_without_label_fallback(self):
        for mutation in ('missing', 'duplicate', 'model', 'action'):
            identity = original_identity()
            if mutation == 'missing': identity['original_xmlids'].pop(0)
            elif mutation == 'duplicate': identity['original_xmlids'].append(copy.deepcopy(identity['original_xmlids'][0]))
            elif mutation == 'model': identity['original_xmlids'][0]['model'] = 'qc.inspection'
            else: identity['ir_ui_menu'][0]['action'] = 'ir.actions.act_window,999'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                probe.original_bindings(identity)

    def test_source_hidden_category_remains_an_actual_result_without_heuristic_or_grant(self):
        bindings = probe.original_bindings(original_identity())
        routes = {key: {**row, 'parent_chain_including_menu': [row['menu']]}
            for key, row in bindings.items()}
        actor = ActorFixture()
        observations, visible = probe.observe_menus(actor, routes, access_error=AccessDenied)
        self.assertEqual(visible, [1, 2, 4])
        self.assertFalse(observations['category']['visible_debug_false'])
        self.assertTrue(observations['category']['normal_menu_id_read_allowed'])
        self.assertTrue(observations['category']['action_model_read_allowed'])
        self.assertEqual(actor.menus.debug_values, [False])
        self.assertEqual(actor.menus.fields, [['id']] * 4)
        self.assertEqual(actor.action_models, [route[-1] for route in probe.ROUTES])
        actor.su = True
        with self.assertRaises(ValueError): probe.observe_menus(actor, routes, access_error=AccessDenied)

    def test_actual_runtime_boundary_has_no_action_execution_registry_load_or_source_mutations(self):
        source = Path(probe.__file__).read_text(encoding='utf-8-sig')
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        methods = {node.func.attr for node in calls if isinstance(node.func, ast.Attribute)}
        self.assertFalse(methods & {'sudo', 'create', 'unlink', 'compute_sheet', 'action_payslip_done',
            'with_user', 'get_payslip_vals', 'new', 'load', 'signal_changes'})
        writes = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == 'write']
        self.assertTrue(all(isinstance(node.func.value, ast.Name) and node.func.value.id == 'stream' for node in writes))
        sql_nodes = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == 'execute']
        self.assertTrue(sql_nodes)
        for node in sql_nodes:
            self.assertTrue(ast.get_source_segment(source, node.args[0]).lstrip().startswith(('\'SELECT', '"SELECT')))
        self.assertIn('db_connect(database, readonly=True).cursor()', source)
        self.assertIn('cr.readonly is True', source)
        self.assertIn("'source_policy_before': policy_before", source)
        self.assertIn('counters_before == counters_after', source)
        self.assertIn('menu_before == menu_after', source)
        self.assertIn("'target_menu_equivalence_certified': False", source)
        self.assertIn('0o600', source)


if __name__ == '__main__':
    unittest.main()
