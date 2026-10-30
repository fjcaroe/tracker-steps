"""Observe four ORIGINAL native menu routes with the sealed source actor.

Preparation only: the coordinator loads the official native registry with the
approved read-only bootstrap, lease and complete process witnesses. This module
does not load a registry, override any source method, execute an action, create
an actor, grant access, or decide whether a target menu is equivalent.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

import original_handover_visibility_contract as visibility
import probe_original_master_visibility as masters


# These bindings come from original_xmlids in the sealed original identity,
# not menu labels or a guess based on the target Community menu names.
ROUTES = (
    ('structure', 'hr_payroll.menu_hr_payroll_structure_view',
        'hr_payroll.action_view_hr_payroll_structure_list_form', 'hr.payroll.structure'),
    ('rule', 'hr_payroll.menu_action_hr_salary_rule_form',
        'hr_payroll.action_salary_rule_form', 'hr.salary.rule'),
    ('category', 'hr_payroll.menu_hr_salary_rule_category',
        'hr_payroll.action_hr_salary_rule_category', 'hr.salary.rule.category'),
    ('input_type', 'hr_payroll.menu_hr_payslip_entry_type_view',
        'hr_payroll.action_view_hr_payslip_input_type', 'hr.payslip.input.type'),
)
ALIAS_COLUMNS = ('id', 'module', 'name', 'model', 'res_id', 'noupdate')
MENU_COLUMNS = ('id', 'parent_id', 'action', 'active')
MENU_POLICY_TABLES = ('ir_ui_menu', 'ir_ui_menu_group_rel', 'ir_act_window',
    'ir_act_window_view', 'ir_actions', 'ir_model_access', 'ir_rule',
    'rule_group_rel', 'ir_model_fields_group_rel', 'res_groups',
    'res_groups_users_rel', 'res_groups_implied_rel', 'res_company_users_rel')


def need(value, code):
    if not value:
        raise ValueError('original-menu-visibility-' + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def sealed_json(path, digest):
    path = Path(path).resolve()
    need(path.is_relative_to(Path('/opt/steps-validation')) and path.is_file()
        and stat.S_IMODE(path.stat().st_mode) == 0o600, 'private-sealed-input-required')
    raw = path.read_bytes()
    need(re.fullmatch('[a-f0-9]{64}', digest) and sha(raw) == digest, 'input-seal-differs')
    return json.loads(raw)


def original_bindings(identity):
    """Resolve exactly four routes using original XML ID, action and model."""
    aliases = identity['original_xmlids']
    menus = {row['id']: row for row in identity['ir_ui_menu']}
    need(len(menus) == len(identity['ir_ui_menu']), 'duplicate-original-menu-id')
    result = {}
    for key, menu_alias, action_alias, model in ROUTES:
        resolved = []
        for alias, target_model in ((menu_alias, 'ir.ui.menu'), (action_alias, 'ir.actions.act_window')):
            module, name = alias.split('.', 1)
            rows = [row for row in aliases if row['module'] == module and row['name'] == name]
            need(len(rows) == 1 and rows[0]['model'] == target_model
                and type(rows[0]['res_id']) is int and rows[0]['res_id'] > 0,
                'missing-ambiguous-or-retargeted-original-alias:' + key)
            resolved.append({column: rows[0][column] for column in ALIAS_COLUMNS})
        menu_xmlid, action_xmlid = resolved
        menu = menus.get(menu_xmlid['res_id'])
        need(menu is not None and menu['action'] == 'ir.actions.act_window,' + str(action_xmlid['res_id']),
            'original-menu-action-binding-differs:' + key)
        result[key] = {'menu_alias': menu_alias, 'action_alias': action_alias, 'model': model,
            'menu_xmlid': menu_xmlid, 'action_xmlid': action_xmlid,
            'menu': {column: menu[column] for column in MENU_COLUMNS}}
    return result


def read_native_routes(cr, identity, bindings):
    """Metadata only; never execute an action, evaluate a domain or read a master."""
    original_menus = {row['id']: row for row in identity['ir_ui_menu']}
    result = {}
    for key, binding in bindings.items():
        for alias in (binding['menu_xmlid'], binding['action_xmlid']):
            cr.execute('SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE module=%s AND name=%s',
                (alias['module'], alias['name']))
            need([dict(zip(ALIAS_COLUMNS, row)) for row in cr.fetchall()] == [alias],
                'current-original-xmlid-differs:' + key)
        cr.execute('SELECT id,res_model,view_mode FROM ir_act_window WHERE id=%s', (binding['action_xmlid']['res_id'],))
        actions = cr.fetchall()
        need(len(actions) == 1 and actions[0][1] == binding['model'] and 'form' in actions[0][2].split(','),
            'actual-native-action-model-or-form-differs:' + key)
        chain, seen, current = [], set(), binding['menu_xmlid']['res_id']
        while current is not None:
            need(current not in seen and current in original_menus, 'original-menu-parent-cycle-or-missing')
            seen.add(current)
            cr.execute('SELECT id,parent_id,action,active FROM ir_ui_menu WHERE id=%s', (current,))
            rows = [dict(zip(MENU_COLUMNS, row)) for row in cr.fetchall()]
            expected = {column: original_menus[current][column] for column in MENU_COLUMNS}
            need(rows == [expected], 'original-menu-route-changed:' + key)
            cr.execute('SELECT gid FROM ir_ui_menu_group_rel WHERE menu_id=%s ORDER BY gid', (current,))
            groups = [row[0] for row in cr.fetchall()]
            original_groups = sorted(row['gid'] for row in identity['ir_ui_menu_group_rel'] if row['menu_id'] == current)
            need(groups == original_groups, 'original-menu-group-policy-changed:' + key)
            chain.append({**expected, 'group_ids': groups})
            current = expected['parent_id']
        result[key] = {**binding, 'action': dict(zip(('id', 'res_model', 'view_mode'), actions[0])),
            'parent_chain_including_menu': chain}
    return result


def menu_policy_snapshot(cr):
    result = {}
    for table in MENU_POLICY_TABLES:
        cr.execute("SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' "
            "ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') FROM " + masters.identifier(table) + ' t')
        count, digest = cr.fetchone()
        result[table] = {'rows': count, 'sha256': digest}
    return result


def observe_menus(actor_env, routes, *, access_error):
    need(not actor_env.su, 'normal-source-actor-required')
    model = actor_env['ir.ui.menu']
    # The actual source method owns visibility semantics. No local group/domain
    # evaluator and no assumption that group_no_one explains a hidden menu.
    visible = model._visible_menu_ids(debug=False)
    need(isinstance(visible, set) and all(type(value) is int for value in visible), 'source-menu-set-invalid')
    observations = {}
    for key, route in routes.items():
        ident = route['menu_xmlid']['res_id']
        try:
            rows = model.browse(ident).read(['id'])
        except access_error:
            readable = False
        else:
            need(rows == [{'id': ident}], 'normal-menu-id-read-invalid')
            readable = True
        access = actor_env['ir.model.access'].check(route['model'], 'read', raise_exception=False)
        observations[key] = {**route, 'visible_debug_false': ident in visible,
            'normal_menu_id_read_allowed': readable, 'action_model_read_allowed': bool(access),
            'parent_visibility': [{'id': row['id'], 'visible_debug_false': row['id'] in visible}
                for row in route['parent_chain_including_menu']]}
    return observations, sorted(visible)


def run(env, *, capsule_path, capsule_sha256, identity_path, identity_sha256,
        source_visibility_path, source_visibility_sha256, output):
    from odoo import api, sql_db
    from odoo.exceptions import AccessError

    database = env.cr.dbname
    need(re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_REFERENCE_[A-Za-z0-9_]+', database),
        'untouched-private-native-reference-required')
    capsule = sealed_json(capsule_path, capsule_sha256)
    identity = sealed_json(identity_path, identity_sha256)
    source = sealed_json(source_visibility_path, source_visibility_sha256)
    need(capsule_sha256 == masters.CAPSULE_SHA256, 'original-capsule-pin-differs')
    visibility.validate_source(source, capsule, target_database=database.replace('_REFERENCE_', '_HANDOVER_'),
        original_model_id=600, original_report_ids=[462])
    bindings = original_bindings(identity)
    output = Path(output).resolve()
    need(output.is_relative_to(Path('/opt/steps-validation')) and output.parent.is_dir()
        and not output.exists(), 'new-private-output-required')
    mro = [klass.__module__ + '.' + klass.__name__ for klass in type(env['hr.payslip']).__mro__]
    need(any(value.startswith('odoo.addons.hr_payroll.') for value in mro)
        and not any(value.startswith('odoo.addons.payroll.') for value in mro), 'actual-original-native-mro-required')
    with sql_db.db_connect(database, readonly=True).cursor() as cr:
        cr.execute("SELECT current_database(),current_setting('transaction_read_only'),current_setting('transaction_isolation'),pg_is_in_recovery()")
        need(cr.fetchone() == (database, 'on', 'repeatable read', False) and cr.readonly is True,
            'actual-native-primary-readonly-repeatable-read-required')
        cr.execute("SELECT name,latest_version,license,state FROM ir_module_module WHERE state='installed' ORDER BY name")
        modules = [dict(zip(('name', 'version', 'license', 'state'), row)) for row in cr.fetchall()]
        need(len(modules) == 381 and sum(row['license'] == 'OEEL-1' for row in modules) == 140
            and sha(masters.encode(modules)) == source['engine']['module_metadata_sha256'],
            'same-untouched381-native140-provider-required')
        cr.execute("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
        need(cr.fetchone() == (0,), 'source-pending-module-operation')
        before = masters.physical_projection(cr)
        policy_before, counters_before = masters.policy_snapshot(cr), masters.counter_snapshot(cr)
        need(before == source['original_sql_projection']
            and policy_before == source['policy_before']
            and counters_before == source['business_counters_before'], 'sealed-source-masters-policy-or-counters-differ')
        menu_before = menu_policy_snapshot(cr)
        routes = read_native_routes(cr, identity, bindings)
        actor = source['actor']
        companies = actor['allowed_company_ids']
        active = actor['active_company_id']
        context = dict(env.context, allowed_company_ids=[active] + [value for value in companies if value != active],
            active_test=False, lang='en_US')
        actor_env = api.Environment(cr, actor['uid'], context, su=False)
        need(not actor_env.su and actor_env.company.id == active
            and sorted(actor_env.user.company_ids.ids) == actor['original_company_memberships']
            and actor_env.user.has_group('hr_payroll.group_hr_payroll_manager')
            and not actor_env.user.has_group('base.group_system'), 'sealed-existing-normal-actor-context-differs')
        observations, visible_ids = observe_menus(actor_env, routes, access_error=AccessError)
        group_ids = sorted(actor_env.user._get_group_ids())
        after = masters.physical_projection(cr)
        policy_after, counters_after = masters.policy_snapshot(cr), masters.counter_snapshot(cr)
        menu_after = menu_policy_snapshot(cr)
        need(before == after and policy_before == policy_after and counters_before == counters_after
            and menu_before == menu_after, 'source-changed-during-menu-observation')
        proof = {'schema': 1, 'profile': 'source-native-original-menu-visibility', 'database': database,
            'probe_sha256': sha(Path(__file__).read_bytes()), 'capsule_sha256': capsule_sha256,
            'identity_sha256': identity_sha256, 'source_visibility_sha256': source_visibility_sha256,
            'source_observer_sha256': source['probe_sha256'], 'actor': actor,
            'trusted_helpers_sha256': {'probe_original_master_visibility.py': sha(Path(masters.__file__).read_bytes()),
                'original_handover_visibility_contract.py': sha(Path(visibility.__file__).read_bytes())},
            'transaction': source['transaction'], 'engine': source['engine'],
            'actual_actor_group_ids': group_ids, 'debug': False, 'menus': observations,
            'actual_visible_menu_ids': visible_ids, 'visible_menu_ids_sha256': sha(masters.encode(visible_ids)),
            'master_projection_sha256_before': sha(masters.encode(before)),
            'master_projection_sha256_after': sha(masters.encode(after)),
            'source_policy_before': policy_before, 'source_policy_after': policy_after,
            'menu_policy_before': menu_before, 'menu_policy_after': menu_after,
            'business_counters_before': counters_before, 'business_counters_after': counters_after,
            'actual_native_method_invoked': 'ir.ui.menu._visible_menu_ids(debug=False)',
            'normal_menu_fields_read': ['id'], 'actions_executed': False,
            'action_domains_evaluated_locally': False, 'source_method_overridden': False,
            'permissions_granted': False, 'database_writes': False, 'historical_payroll_read': False,
            'salary_amounts_read': False, 'formula_bodies_read_from_database': False,
            'salary_rules_evaluated': False, 'target_menu_equivalence_certified': False,
            'financial_certified': False, 'identity_conversion': False, 'all_products_operational': False,
            'deadline_resolved': False}
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(json.dumps(proof, indent=2, ensure_ascii=False).encode())
    return proof
