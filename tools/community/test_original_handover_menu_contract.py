"""Synthetic menu receipt boundaries, never a Source or Target runtime oracle."""
from copy import deepcopy
import unittest

import original_handover_menu_contract as contract
import probe_original_menu_visibility as native
import probe_original_handover as probe
import resume_original_anchor_probe as resumer
from test_original_handover_visibility_contract import fixture as master_fixture
from test_probe_original_menu_visibility import original_identity


def fixture():
    capsule, source = master_fixture(); identity = original_identity()
    bindings = native.original_bindings(identity)
    visible = [row['menu_xmlid']['res_id'] for key, row in bindings.items() if key != 'rule']
    routes = {}
    for key, binding in bindings.items():
        ident = binding['menu_xmlid']['res_id']; action_id = binding['action_xmlid']['res_id']
        routes[key] = dict(binding, action={'id': action_id, 'res_model': binding['model'], 'view_mode': 'list,form'},
            parent_chain_including_menu=[dict(binding['menu'], group_ids=[])],
            visible_debug_false=ident in visible, normal_menu_id_read_allowed=True, action_model_read_allowed=True,
            parent_visibility=[{'id': ident, 'visible_debug_false': ident in visible}])
    policy = {name: {'rows': 1, 'sha256': 'a' * 64} for name in native.MENU_POLICY_TABLES}
    proof = {'schema': 1, 'profile': 'source-native-original-menu-visibility',
        'database': source['database'], 'probe_sha256': next(iter(contract.SOURCE_HASHES)),
        'capsule_sha256': source['capsule_sha256'], 'identity_sha256': 'b' * 64,
        'source_visibility_sha256': 'c' * 64, 'source_observer_sha256': source['probe_sha256'],
        'engine': source['engine'], 'transaction': source['transaction'], 'actor': source['actor'],
        'trusted_helpers_sha256': {'probe_original_master_visibility.py': source['probe_sha256'],
            'original_handover_visibility_contract.py': next(iter(contract.VISIBILITY_HASHES))},
        'debug': False, 'actual_native_method_invoked': 'ir.ui.menu._visible_menu_ids(debug=False)',
        'normal_menu_fields_read': ['id'], 'source_policy_before': source['policy_before'],
        'source_policy_after': source['policy_after'], 'business_counters_before': source['business_counters_before'],
        'business_counters_after': source['business_counters_after'],
        'master_projection_sha256_before': source['original_sql_projection_sha256'],
        'master_projection_sha256_after': source['original_sql_projection_sha256'],
        'menu_policy_before': policy, 'menu_policy_after': deepcopy(policy),
        'actual_visible_menu_ids': visible, 'visible_menu_ids_sha256': contract.sha(native.masters.encode(visible)),
        'actual_actor_group_ids': [1, 46], 'menus': routes}
    for name in ('actions_executed', 'action_domains_evaluated_locally', 'source_method_overridden',
        'permissions_granted', 'database_writes', 'historical_payroll_read', 'salary_amounts_read',
        'formula_bodies_read_from_database', 'salary_rules_evaluated', 'target_menu_equivalence_certified',
        'financial_certified', 'identity_conversion', 'all_products_operational', 'deadline_resolved'):
        proof[name] = False
    return proof, source, identity


class SourceMenuContractCase(unittest.TestCase):
    def validate(self, proof, source, identity):
        return contract.validate_source(proof, source, identity, source_sha256='c' * 64, identity_sha256='b' * 64)

    def test_concepts_derive_hidden_result_from_source_without_country_or_technical_group(self):
        proof, source, identity = fixture()
        self.validate(proof, source, identity)
        # This synthetic source hides RULE, not CATEGORY. No group/domain
        # heuristic or special case can change that recorded expectation.
        self.assertFalse(proof['menus']['rule']['visible_debug_false'])
        self.assertTrue(proof['menus']['category']['visible_debug_false'])
        for row in proof['menus'].values():
            actual = {key: row[key] for key in ('model', 'visible_debug_false',
                'normal_menu_id_read_allowed', 'action_model_read_allowed')}
            contract.compare_facets(row, actual)
            for name in ('visible_debug_false', 'normal_menu_id_read_allowed', 'action_model_read_allowed'):
                changed = dict(actual); changed[name] = not changed[name]
                with self.subTest(name=name), self.assertRaises(ValueError): contract.compare_facets(row, changed)

    def test_source_seals_actor_engine_aliases_original_parents_and_policies_fail_closed(self):
        proof, source, identity = fixture()
        for change in ('tool', 'masterseal', 'identityseal', 'epoch', 'actor', 'engine', 'readonly',
                       'grant', 'policy', 'menupolicy', 'counter', 'alias', 'parent', 'observation', 'debug'):
            value = deepcopy(proof)
            if change == 'tool': value['probe_sha256'] = 'd' * 64
            elif change == 'masterseal': value['source_visibility_sha256'] = 'd' * 64
            elif change == 'identityseal': value['identity_sha256'] = 'd' * 64
            elif change == 'epoch': value['database'] += '_OTHER'
            elif change == 'actor': value['actor'] = dict(value['actor'], uid=99)
            elif change == 'engine': value['engine'] = dict(value['engine'], enterprise=0)
            elif change == 'readonly': value['transaction'] = dict(value['transaction'], read_only=False)
            elif change == 'grant': value['permissions_granted'] = True
            elif change == 'policy': value['source_policy_after']['res_groups']['rows'] += 1
            elif change == 'menupolicy': value['menu_policy_after']['ir_ui_menu']['rows'] += 1
            elif change == 'counter': value['business_counters_after']['ir_sequence_1'][0] += 1
            elif change == 'alias': value['menus']['rule']['action_xmlid']['res_id'] = 999
            elif change == 'parent': value['menus']['rule']['parent_chain_including_menu'][0]['group_ids'] = [999]
            elif change == 'observation': value['menus']['rule']['visible_debug_false'] = True
            else: value['debug'] = True
            with self.subTest(change=change), self.assertRaises(ValueError): self.validate(value, source, identity)

    def test_witness_is_optional_for_full_but_never_implicit_or_projection_scope(self):
        probe.menu_witness_arguments('full', None, None, None, None)
        probe.menu_witness_arguments('full', '/sealed/source', 'a' * 64, '/sealed/menus', 'b' * 64)
        for args in (('projection-only', '/source', 'a' * 64, '/menus', 'b' * 64),
            ('full', None, None, '/menus', 'b' * 64), ('full', '/source', 'a' * 64, None, 'b' * 64),
            ('full', '/source', 'a' * 64, '/menus', None)):
            with self.assertRaises(probe.ProbeBlocked): probe.menu_witness_arguments(*args)
        base = ['--root', '/private/root', '--tools', '/private/tools', '--source-visibility', '/private/source',
            '--attempt', 'new', '--source-menu-visibility', '/private/menus', '--source-menu-sha256', 'b' * 64]
        options = resumer.parse_arguments(base)
        self.assertEqual(options.admission_scope, 'full')
        self.assertEqual(str(options.source_menu_visibility).replace('\\', '/'), '/private/menus')


if __name__ == '__main__':
    unittest.main()
