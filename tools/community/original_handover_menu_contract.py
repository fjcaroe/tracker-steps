"""Consume actual native menu observations, never infer a technical exception.

Source helper 2c9adbee/3bdf41e5 has the same Git bytes. Only its sealed actual
result, tied to the master source witness and original identity, may define
expected visibility. No domain execution, group grant or action execution.
"""
import hashlib
import importlib
from pathlib import Path
import re

import original_handover_visibility_contract as visibility


SOURCE_HASHES = {
    '1f0459b1633abaace98ee81b982fbc6d5c1589faac2bcacabfb1421a3403e2fe',  # U29 LF
    '894bff524985565aee11713634d323352f4792f34fcac1fb33ee6672d766b515',  # U29 CRLF
    '3a3d3dcea469f223ba1e120e909a6c54435619e7abc7c4b65f4f7f778e9337b3',
    'ef162f6989f1aa171a018c36d01b208a0dc0a63e03c6bc886a34e12da9f61056'}
VISIBILITY_HASHES = {
    'ab4a81ad1c5309cfccaa39dbdd88bde1f073287bad706a0ee862ad79bf77b223',  # U40 LF
    '5dae942ca169212a8b0f47d79af2761b9ba93a80ad90f12f12a12caf6528111b',  # U40 CRLF
    'ce81c5aa46534db1a34c032e7a29cd3eae2ccbad0f8e3d92ce7d45d0e580cb02',  # U29 LF
    '271e005243466928533e8b8c57b8bfa03427325f79b276dcc5fee6d02d17f698',  # U29 CRLF
    '70b8be19c2cd9d10c7746b851cfd839af9bd119d08fe255dfe8c9afedd347385',  # U11 Git LF
    '5a379c79b812a1adc05862b13e7ba465f51d111fe02785c69d181bf49a01926c',  # U11 CRLF
'bee6eb555ce906c7879b74d02fb3d03117a76662665e1c29d08f9647dbd8aa59',
    'afa2d84e04ead0336df33dab20c478966184f70632cced044db28fa81fd526b5',
    '91474b56be987ecfa0c133a6416b9d63fa8116eba8a29b57a8435e8c79e26c1b',  # U13 Git LF
    'd920f270c52313e18a90c44c02a213a0808c4c40061ec124a19e4f7a24793018',  # U13 CRLF
}
TARGET_ROUTES = (
    ('structure', 'payroll.hr_payroll_structure_menu', 'payroll.hr_payroll_structure_action', 'hr.payroll.structure'),
    ('rule', 'payroll.menu_action_hr_salary_rule_form', 'payroll.action_salary_rule_form', 'hr.salary.rule'),
    ('category', 'payroll.menu_hr_salary_rule_category', 'payroll.hr_salary_rule_category_action', 'hr.salary.rule.category'),
    ('input_type', 'step_payroll_oca_api.original_input_type_menu',
        'step_payroll_oca_api.original_input_type_action', 'hr.payslip.input.type'),
)


class MenuWitnessBlocked(ValueError):
    pass


def need(value, code):
    if not value:
        raise MenuWitnessBlocked('original-source-menu-' + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def observer():
    module = importlib.import_module('probe_original_menu_visibility')
    need(sha(Path(module.__file__).read_bytes()) in SOURCE_HASHES, 'observer-does-not-match-approved-git')
    return module


def validate_source(proof, source, identity, *, source_sha256, identity_sha256):
    native = observer()
    need(proof.get('schema') == 1 and proof.get('profile') == 'source-native-original-menu-visibility'
        and proof.get('probe_sha256') in SOURCE_HASHES, 'actual-approved-native-menu-observer-required')
    need(proof.get('database') == source['database'] and proof.get('capsule_sha256') == source['capsule_sha256']
        and proof.get('identity_sha256') == identity_sha256
        and proof.get('source_visibility_sha256') == source_sha256
        and proof.get('source_observer_sha256') == source['probe_sha256'], 'source-epoch-or-input-seals-differ')
    need(proof.get('engine') == source['engine'] and proof.get('transaction') == source['transaction']
        and proof.get('actor') == source['actor'], 'real-native-engine-cursor-or-normal-actor-differs')
    helpers = proof.get('trusted_helpers_sha256', {})
    need(set(helpers) == {'probe_original_master_visibility.py', 'original_handover_visibility_contract.py'}
        and helpers['probe_original_master_visibility.py'] in visibility.SOURCE_OBSERVER_HASHES
        and helpers['original_handover_visibility_contract.py'] in VISIBILITY_HASHES,
        'source-helper-provenance-differs')
    need(proof.get('debug') is False and proof.get('actual_native_method_invoked')
        == 'ir.ui.menu._visible_menu_ids(debug=False)' and proof.get('normal_menu_fields_read') == ['id'],
        'actual-normal-source-menu-method-required')
    for name in ('actions_executed', 'action_domains_evaluated_locally', 'source_method_overridden',
        'permissions_granted', 'database_writes', 'historical_payroll_read', 'salary_amounts_read',
        'formula_bodies_read_from_database', 'salary_rules_evaluated', 'target_menu_equivalence_certified',
        'financial_certified', 'identity_conversion', 'all_products_operational', 'deadline_resolved'):
        need(proof.get(name) is False, 'unproven-or-unsafe-source-flag:' + name)
    need(proof.get('source_policy_before') == proof.get('source_policy_after') == source['policy_before']
        and proof.get('business_counters_before') == proof.get('business_counters_after')
        == source['business_counters_before'], 'source-original-security-or-counters-differ')
    projection = source['original_sql_projection_sha256']
    need(proof.get('master_projection_sha256_before') == proof.get('master_projection_sha256_after') == projection,
        'source-original-master-projection-differs')
    policy = proof.get('menu_policy_before', {})
    need(set(policy) == set(native.MENU_POLICY_TABLES) and policy == proof.get('menu_policy_after'),
        'source-menu-policy-not-preserved')
    need(all(type(row.get('rows')) is int and row['rows'] >= 0
        and re.fullmatch('[a-f0-9]{64}', row.get('sha256', '')) for row in policy.values()), 'invalid-source-policy-hash')
    visible = proof.get('actual_visible_menu_ids')
    groups = proof.get('actual_actor_group_ids')
    need(visibility.ids(visible) and visibility.ids(groups) and groups
        and proof.get('visible_menu_ids_sha256') == sha(native.masters.encode(visible)),
        'source-visible-id-set-or-group-binding-differs')
    expected = native.original_bindings(identity)
    need(set(proof.get('menus', {})) == set(expected), 'exact-four-source-concepts-required')
    original_menus = {row['id']: row for row in identity['ir_ui_menu']}
    for key, binding in expected.items():
        actual = proof['menus'][key]
        need(all(actual.get(name) == value for name, value in binding.items()), 'original-source-route-retargeted:' + key)
        action = actual.get('action', {})
        need(action.get('id') == binding['action_xmlid']['res_id'] and action.get('res_model') == binding['model']
            and 'form' in action.get('view_mode', '').split(','), 'source-action-model-or-form-differs:' + key)
        chain, seen, current = [], set(), binding['menu_xmlid']['res_id']
        while current is not None:
            need(current not in seen and current in original_menus, 'source-parent-chain-invalid')
            seen.add(current); row = original_menus[current]
            chain.append({**{column: row[column] for column in native.MENU_COLUMNS},
                'group_ids': sorted(link['gid'] for link in identity['ir_ui_menu_group_rel'] if link['menu_id'] == current)})
            current = row['parent_id']
        need(actual.get('parent_chain_including_menu') == chain, 'source-menu-parent-or-group-policy-differs:' + key)
        need(actual.get('parent_visibility') == [{'id': row['id'], 'visible_debug_false': row['id'] in visible}
            for row in chain], 'source-parent-visibility-not-observed:' + key)
        need(type(actual.get('visible_debug_false')) is bool
            and actual['visible_debug_false'] == (binding['menu_xmlid']['res_id'] in visible)
            and type(actual.get('normal_menu_id_read_allowed')) is bool
            and type(actual.get('action_model_read_allowed')) is bool, 'source-menu-observation-invalid:' + key)
    return native


def compare_facets(source, target):
    for name in ('visible_debug_false', 'normal_menu_id_read_allowed', 'action_model_read_allowed'):
        need(type(target.get(name)) is bool and target[name] == source[name], 'actual-target-parity-differs:' + name)
    need(target.get('model') == source['model'], 'actual-target-action-model-differs')


def observe_target(scope, proof, *, access_error):
    need(not scope.su and scope.uid == proof['actor']['uid'], 'same-normal-target-actor-required')
    need(sorted(scope.user._get_group_ids()) == proof['actual_actor_group_ids'], 'actual-target-actor-groups-differ')
    visible = scope['ir.ui.menu']._visible_menu_ids(debug=False)
    need(isinstance(visible, set) and all(type(value) is int for value in visible), 'actual-target-menu-set-invalid')
    result = []
    for key, menu_alias, action_alias, model in TARGET_ROUTES:
        source = proof['menus'][key]
        menu = scope.ref(menu_alias, raise_if_not_found=False)
        action = scope.ref(action_alias, raise_if_not_found=False)
        need(menu and menu._name == 'ir.ui.menu' and action and action._name == 'ir.actions.act_window',
            'real-target-menu-and-action-aliases-required:' + key)
        # Metadata route binding is distinct from the actor's actual id-only
        # read below; no sudo record read or action/domain execution.
        scope.cr.execute('SELECT action,active FROM ir_ui_menu WHERE id=%s', [menu.id])
        need(scope.cr.fetchall() == [('ir.actions.act_window,' + str(action.id), True)],
            'target-menu-does-not-point-to-exact-concept-action:' + key)
        configured = scope['ir.actions.actions']._for_xml_id(action_alias)
        need(configured.get('id') == action.id and configured.get('res_model') == model
            and 'form' in configured.get('view_mode', '').split(','), 'target-action-model-or-form-differs:' + key)
        try:
            records = menu.read(['id'])
        except access_error:
            readable = False
        else:
            need(records == [{'id': menu.id}], 'target-menu-id-read-invalid:' + key)
            readable = True
        actual = {'concept': key, 'model': model, 'menu_id': menu.id, 'action_id': action.id,
            'menu_alias': menu_alias, 'action_alias': action_alias, 'visible_debug_false': menu.id in visible,
            'normal_menu_id_read_allowed': readable,
            'action_model_read_allowed': bool(scope['ir.model.access'].check(model, 'read', raise_exception=False))}
        compare_facets(source, actual)
        result.append(dict(actual, source_menu_id=source['menu_xmlid']['res_id'],
            source_action_id=source['action_xmlid']['res_id'], actual_native_target_parity=True,
            visibility_derived_from_sealed_native_observation=True, permissions_granted=False,
            action_executed=False, full_flow_certified=False))
    return result
