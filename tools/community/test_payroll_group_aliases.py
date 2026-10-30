"""Bounded alias normalization policy; runtime Odoo tests exercise real groups/UI."""
import ast
from pathlib import Path
import unittest
from types import SimpleNamespace


class AliasAccessError(Exception):
    pass


def policy():
    path = Path(__file__).resolve().parents[2] / 'step_payroll_contracts/group_aliases.py'
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    nodes = [node for node in tree.body if
        isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'ROLE_PAIRS' for target in node.targets)
        or isinstance(node, ast.ClassDef) and node.name == 'PayrollGroupDefinitions'
        or isinstance(node, ast.FunctionDef) and node.name == 'verified_role_definitions']
    scope = {'AccessError': AliasAccessError}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), 'exec'), scope)
    return scope['verified_role_definitions'], scope['ROLE_PAIRS']


class Core:
    def __init__(self, refs):
        self.refs, self.calls = refs, []
        self.empty, self.universe = object(), object()

    def get_id(self, ref):
        return self.refs.get(ref)

    def parse(self, refs, raise_if_not_found=True):
        self.calls.append(('parse', refs, raise_if_not_found))
        return self.calls[-1]

    def from_ids(self, *args):
        return ('core_ids', args)

    def from_key(self, key):
        return ('core_key', key)


def fixture(reverse=False):
    function, pairs = policy()
    rows, refs = [], {'base.group_user': 1}
    for ident, (original, alias) in enumerate(pairs, 10):
        rows += [(original, 'res.groups', ident, ident), (alias, 'res.groups', ident, ident)]
        refs[alias if reverse else original] = ident
    return function, pairs, rows, Core(refs)


def constraint_policy():
    path = Path(__file__).resolve().parents[2] / 'step_payroll_contracts/group_aliases.py'
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
        and node.name == '_queue_original_rule_group_constraint']
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), 'exec'), scope)
    return scope['_queue_original_rule_group_constraint']


class RuleConstraintPolicyCase(unittest.TestCase):
    def fixture(self, **changes):
        calls = []
        def updater(model):
            calls.append(('actual_original_field_updater', model))
        values = dict(type='many2many', comodel_name='res.groups', relation='rule_group_rel',
            column1='rule_group_id', column2='group_id', ondelete='restrict', update_db_foreign_keys=updater)
        values.update(changes)
        rules = SimpleNamespace(_fields={'groups': SimpleNamespace(**values)})
        queue = [('existing_inverse_updater',)]
        groups = SimpleNamespace(env={'ir.rule': rules},
            pool=SimpleNamespace(post_init=lambda function, model: queue.append((function, model))))
        return groups, rules, queue, updater, calls

    def test_original_real_updater_is_queued_after_inverse_and_only_delegated_on_execution(self):
        groups, rules, queue, updater, calls = self.fixture()
        constraint_policy()(groups)
        self.assertEqual(queue, [('existing_inverse_updater',), (updater, rules)])
        self.assertEqual(calls, [])
        queue[1][0](queue[1][1])
        self.assertEqual(calls, [('actual_original_field_updater', rules)])

    def test_changed_owner_inverse_target_or_policy_cannot_enqueue_a_guessed_constraint(self):
        for changes in ({'type': 'one2many'}, {'comodel_name': 'ir.rule'}, {'relation': 'other_rel'},
                {'column1': 'group_id'}, {'column2': 'rule_group_id'}, {'ondelete': 'cascade'}):
            groups, rules, queue, updater, calls = self.fixture(**changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError, 'requires review'):
                constraint_policy()(groups)
            self.assertEqual(queue, [('existing_inverse_updater',)])
            self.assertEqual(calls, [])


class PayrollAliasPolicyCase(unittest.TestCase):
    def test_exact_pairs_reuse_real_ids_and_public_core_parse_for_both_canonical_orders(self):
        for reverse in (False, True):
            function, pairs, rows, core = fixture(reverse)
            result = function(core, rows)
            for ident, (original, alias) in enumerate(pairs, 10):
                self.assertEqual(result.get_id(original), ident)
                self.assertEqual(result.get_id(alias), ident)
                canonical = alias if reverse else original
                self.assertEqual(result.parse(alias + ',!base.group_user'), ('parse', canonical + ',!base.group_user', True))
                self.assertEqual(result.parse('!' + original, False), ('parse', '!' + canonical, False))
            self.assertEqual(core.refs, fixture(reverse)[3].refs)

    def test_normal_community_with_only_real_payroll_names_is_the_unmodified_core(self):
        function, pairs, rows, core = fixture(True)
        rows = [row for row in rows if row[0].startswith('payroll.')]
        self.assertIs(function(core, rows), core)

    def test_conflicting_alias_cannot_grant_positive_or_negated_permission(self):
        function, pairs, rows, core = fixture()
        alias = pairs[0][1]
        rows[1] = (alias, 'res.groups', 99, 99)
        result = function(core, rows)
        self.assertEqual(result.get_id(pairs[0][0]), 10)
        with self.assertRaises(AliasAccessError): result.get_id(alias)
        with self.assertRaises(AliasAccessError): result.parse(alias, False)
        with self.assertRaises(AliasAccessError): result.parse('!' + alias, False)
        self.assertEqual(result.get_id('base.group_user'), 1)

    def test_cached_core_does_not_cache_changed_alias_map(self):
        function, pairs, rows, core = fixture()
        self.assertEqual(function(core, rows).get_id(pairs[0][1]), 10)
        rows[1] = (pairs[0][1], 'res.groups', 99, 99)
        with self.assertRaises(AliasAccessError): function(core, rows).get_id(pairs[0][1])
        self.assertEqual(core.get_id(pairs[0][0]), 10)

    def test_missing_or_non_group_target_and_third_unknown_canonical_fail_closed(self):
        function, pairs, rows, core = fixture()
        for change in ('missing', 'wrong_model', 'dangling', 'third_ref', 'cached_wrong_id'):
            changed = list(rows); refs = dict(core.refs)
            if change == 'missing': changed.pop(1)
            if change == 'wrong_model': changed[1] = (pairs[0][1], 'res.partner', 10, None)
            if change == 'dangling': changed[1] = (pairs[0][1], 'res.groups', 10, None)
            if change == 'third_ref': refs.pop(pairs[0][0]); refs['third.original'] = 10
            if change == 'cached_wrong_id': refs[pairs[0][1]] = 99
            with self.subTest(change=change), self.assertRaises(AliasAccessError):
                function(Core(refs), changed).get_id(pairs[0][1])

    def test_unrelated_tokens_unknowns_whitespace_and_all_other_public_methods_delegate_literally(self):
        function, pairs, rows, core = fixture()
        result = function(core, rows)
        self.assertIs(result.empty, core.empty)
        self.assertIs(result.universe, core.universe)
        self.assertEqual(result.from_ids([10]), core.from_ids([10]))
        self.assertEqual(result.from_key('((10,False),)'), core.from_key('((10,False),)'))
        spec = 'unknown.group,!base.group_user, payroll.group_payroll_user'
        self.assertEqual(result.parse(spec, False), ('parse', spec, False))
        self.assertIsNone(result.get_id('unknown.group'))


if __name__ == '__main__':
    unittest.main()
