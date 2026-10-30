"""Read-only proof of exactly five Treasury launcher action changes.

Raw snapshots and both identity contracts remain immutable. The returned copy
only restores five approved ``ir_ui_menu.action`` values for the subsequent
canonical identity verifier; no other table/property is normalized here.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


CORE = 'step_account_treasury'
BRIDGE = 'step_account_treasury_reports'
COMMUNITY = 'step_treasury_community_reports'
KINDS = ('bank', 'ledger', 'cash', 'receivable', 'payable')
MENUS = ('menu_treasury_bank_reconciliation', 'menu_treasury_partner_ledger',
         'menu_treasury_cash_flow_statement', 'menu_treasury_aged_receivable',
         'menu_treasury_aged_payable')
LEGACY_ACTIONS = ('action_account_report_bank_reconciliation',
                  'action_account_report_partner_ledger', 'action_account_report_cs',
                  'action_account_report_ar', 'action_account_report_ap')
GROUPS = ('group_account_readonly', 'group_account_manager')
AUDIT_COLUMNS = {'write_uid', 'write_date'}
CLIENT_TIMESTAMP_XMLIDS = (
    ('step_account_treasury', 'action_treasury_dashboard'),
    ('step_qa', 'action_step_qa_dashboard'),
    ('step_bpa_irrigation', 'action_step_bpa_dashboard'),
    ('step_export', 'action_step_export_dashboard'),
    ('step_packing_operations', 'action_packing_dashboard'),
    ('step_export_control', 'documents_action'),
    ('step_export_control', 'vessels_action'),
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def _quoted(values):
    # Only the fixed module/name literals above enter these SELECT statements.
    return ','.join("'" + value.replace("'", "''") + "'" for value in values)


def snapshot(sql, database):
    """Catalog/UI metadata only; caller supplies its existing readonly SQL API.

    No business rows, balances or payments are read. Full raw rows include audit
    columns, even though the canonical identity witness excludes write audit.
    """
    menu_scope = "d.module='%s' AND d.name IN (%s)" % (CORE, _quoted(MENUS))
    action_scope = "d.module='%s' AND d.name IN (%s)" % (
        COMMUNITY, _quoted('action_' + kind for kind in KINDS))
    legacy_scope = "d.module='account_reports' AND d.name IN (%s)" % _quoted(LEGACY_ACTIONS)
    menu_ids = "SELECT d.res_id FROM ir_model_data d WHERE d.model='ir.ui.menu' AND " + menu_scope
    action_ids = "SELECT d.res_id FROM ir_model_data d WHERE d.model='ir.actions.act_window' AND " + action_scope
    selections = {
        'menu_aliases': 'SELECT d.* FROM ir_model_data d WHERE ' + menu_scope,
        'menus': 'SELECT m.* FROM ir_ui_menu m WHERE m.id IN (' + menu_ids + ')',
        'menu_groups': 'SELECT r.* FROM ir_ui_menu_group_rel r WHERE r.menu_id IN (' + menu_ids + ')',
        'global_client_actions': 'SELECT a.* FROM ir_act_client a',
        'legacy_action_aliases': 'SELECT d.* FROM ir_model_data d WHERE ' + legacy_scope,
        'community_action_aliases': 'SELECT d.* FROM ir_model_data d WHERE ' + action_scope,
        'community_actions': 'SELECT a.* FROM ir_act_window a WHERE a.id IN (' + action_ids + ')',
        'community_action_groups': 'SELECT r.* FROM ir_act_window_group_rel r WHERE r.act_id IN (' + action_ids + ')',
        'account_group_aliases': "SELECT d.* FROM ir_model_data d WHERE d.module='account' AND d.name IN (%s)" % _quoted(GROUPS),
    }
    queries = ["SELECT '%s' AS name,coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) AS value FROM (%s) t" % (key, query)
               for key, query in selections.items()]
    result = json.loads(sql(database, 'SELECT json_object_agg(name,value) FROM (' + ' UNION ALL '.join(queries) + ') t'))
    return dict(result, schema=1)


def _assignments(path):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    return {node.targets[0].id: node.value for node in tree.body if isinstance(node, ast.Assign)
            and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}


def source_contract(source_root=None):
    root = Path(source_root) if source_root is not None else Path(__file__).resolve().parents[2]
    files = ('step_account_treasury/report_ownership.py',
             'step_treasury_community_reports/hooks.py',
             'step_treasury_community_reports/views/reports.xml',
             'step_treasury_community_reports/models/reports.py',
             'step_account_treasury_reports/__manifest__.py')
    ownership = _assignments(root / files[0])
    require(ast.literal_eval(ownership['CORE']) == CORE and ast.literal_eval(ownership['BRIDGE']) == BRIDGE
            and ast.literal_eval(ownership['COMMUNITY']) == COMMUNITY
            and ast.literal_eval(ownership['MENUS']) == MENUS, 'Treasury source ownership allowlist changed')
    launchers = _assignments(root / files[1])
    require(ast.literal_eval(launchers['MODULE']) == COMMUNITY, 'Community source namespace changed')
    require(tuple((row[0], row[1]) for row in ast.literal_eval(launchers['LAUNCHERS'])) == tuple(zip(MENUS, KINDS)),
            'Community source launcher mapping changed')
    manifest = ast.literal_eval((root / files[4]).read_text(encoding='utf-8-sig'))
    require(manifest['depends'] == [COMMUNITY], 'Original bridge does not use only the real Community provider')
    records = {node.attrib['id']: node for node in ET.parse(root / files[2]).getroot().findall('record')}
    for kind in KINDS:
        record = records['action_' + kind]
        require(record.attrib['model'] == 'ir.actions.act_window', 'Community action source model changed')
        fields = {field.attrib['name']: field.text for field in record.findall('field')}
        require(fields['res_model'] == 'step.treasury.report' and fields['view_mode'] == 'form'
                and fields['target'] == 'current' and ast.literal_eval(fields['context']) == {'default_kind': kind},
                'Community action source contract changed')
        groups = next(field.attrib['eval'] for field in record.findall('field') if field.attrib['name'] == 'groups_id')
        group_tree = ast.parse(groups, mode='eval').body
        require(isinstance(group_tree, ast.List) and len(group_tree.elts) == 2, 'Unexpected action source role commands')
        extracted = []
        for command in group_tree.elts:
            require(isinstance(command, ast.Tuple) and len(command.elts) == 2 and ast.literal_eval(command.elts[0]) == 4,
                    'Unexpected action source role operation')
            call = command.elts[1]
            require(isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'ref'
                    and len(call.args) == 1 and not call.keywords, 'Unexpected action source role reference')
            extracted.append(ast.literal_eval(call.args[0]))
        require(extracted == ['account.' + name for name in GROUPS], 'Community action source roles changed')
    return {'files_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files},
            'menu_kind_mapping': dict(zip(MENUS, KINDS))}


def _by_id(rows, label):
    require(isinstance(rows, list) and all(isinstance(row, dict) and type(row.get('id')) is int for row in rows),
            label + ': expected complete integer-ID rows')
    result = {row['id']: row for row in rows}
    require(len(result) == len(rows), label + ': duplicate row ID')
    return result


def _aliases(rows, module, names, model, label, complete=True):
    _by_id(rows, label)
    result = {}
    for row in rows:
        require(row.get('module') == module and row.get('name') in names and row.get('model') == model
                and type(row.get('res_id')) is int and type(row.get('noupdate')) is bool,
                label + ': unexpected namespace/name/model/target/flag')
        require(row['name'] not in result, label + ': duplicate XMLID')
        result[row['name']] = row
    require(not complete or set(result) == set(names), label + ': missing expected XMLID')
    return result


def _existing_exact(before, after, label):
    current = _by_id(after, label)
    for ident, row in _by_id(before, label).items():
        require(current.get(ident) == row, label + ': original row changed ' + str(ident))


def _identity_menu(row):
    return {key: value for key, value in row.items() if key not in AUDIT_COLUMNS}


def _client_action_timestamps(original_identity, current_identity, before, after):
    """Seven loader timestamps only; never exempt values, UID or EE actions.

    IDs are discovered from the original, immutable XMLID witness. No database
    numeric action IDs are an admission criterion. The complete original rows,
    including flags and alias targets, must remain bound to current identity.
    """
    original_actions = _by_id(before, 'original global client actions')
    current_actions = _by_id(after, 'current global client actions')
    require(original_actions.keys() == current_actions.keys(), 'Global client action ID inventory changed')
    current_aliases = _by_id(current_identity['original_xmlids'], 'current original XMLIDs')
    allowed = {}
    report_ids = {row['res_id'] for row in original_identity['original_xmlids']
                  if row.get('module') == 'account_reports' and row.get('model') == 'ir.actions.client'}
    for module, name in CLIENT_TIMESTAMP_XMLIDS:
        aliases = [row for row in original_identity['original_xmlids']
                   if (row.get('module'), row.get('name')) == (module, name)]
        require(len(aliases) == 1, 'Original timestamp action XMLID missing or duplicated: ' + module + '.' + name)
        alias = aliases[0]
        require(alias.get('model') == 'ir.actions.client' and type(alias.get('res_id')) is int
                and alias['res_id'] in original_actions and alias['res_id'] not in allowed
                and (type(alias.get('noupdate')) is bool or alias.get('noupdate') is None)
                and current_aliases.get(alias['id']) == alias,
                'Original timestamp action alias model/ID/binding/flag changed')
        require(alias['res_id'] not in report_ids, 'Enterprise report client actions must remain raw exact')
        allowed[alias['res_id']] = alias
    changes = []
    for ident, row in original_actions.items():
        current = current_actions[ident]
        if current == row:
            continue
        alias = allowed.get(ident)
        require(alias is not None and 'write_date' in row and 'write_date' in current
                and isinstance(current['write_date'], str) and current['write_date']
                and dict(current, write_date=row['write_date']) == row,
                'Unapproved global client action value/UID/timestamp changed')
        changes.append({'xmlid': alias['module'] + '.' + alias['name'], 'action_id': ident,
                        'original_xmlid_id': alias['id'], 'original_noupdate': alias['noupdate'],
                        'before_write_date': row['write_date'], 'after_write_date': current['write_date'],
                        'all_other_raw_columns_exact': True})
    return {'original_global_client_actions_exact': not changes,
            'original_global_client_actions_functional_exact': True,
            'approved_client_action_write_date_changes': sorted(changes, key=lambda row: row['xmlid']),
            'global_client_action_count_preserved': len(original_actions)}


def verify(original_identity, current_identity, before, after, source_root=None):
    """Return ``(audit, normalized_current)``; never modify any supplied object.

    Other identity tables are passed through verbatim for the caller's remaining
    source-specific HR policies and canonical strict verifier. This helper does
    not license or conceal their differences.
    """
    source = source_contract(source_root)
    require(before.get('schema') == after.get('schema') == 1, 'Unsupported launcher snapshot schema')
    original_aliases = _aliases(before['menu_aliases'], CORE, MENUS, 'ir.ui.menu', 'original menu aliases')
    current_aliases = _aliases(after['menu_aliases'], CORE, MENUS, 'ir.ui.menu', 'current menu aliases')
    require(original_aliases == current_aliases, 'Original Treasury XMLID rows/flags changed')
    _existing_exact(original_identity['original_xmlids'], current_identity['original_xmlids'], 'all original XMLIDs')
    for label, identity, captured in (('original', original_identity, before), ('current', current_identity, after)):
        identity_aliases = _by_id(identity['original_xmlids'], label + ' XMLIDs')
        for key in ('menu_aliases', 'legacy_action_aliases', 'community_action_aliases', 'account_group_aliases'):
            for row in captured[key]:
                projected = identity_aliases.get(row['id'])
                require(projected is not None and {'id', 'module', 'name', 'model', 'res_id', 'noupdate'} <= set(projected)
                        and all(row.get(prop) == value for prop, value in projected.items()),
                        'Launcher alias snapshot is not bound to ' + label + ' identity')
    client_action_audit = _client_action_timestamps(original_identity, current_identity,
        before['global_client_actions'], after['global_client_actions'])
    _existing_exact(before['legacy_action_aliases'], after['legacy_action_aliases'], 'legacy global action aliases')
    _existing_exact(before['account_group_aliases'], after['account_group_aliases'], 'accounting roles')
    require(before['menu_groups'] == after['menu_groups'], 'Original launcher group relations changed')
    legacy = _aliases(before['legacy_action_aliases'], 'account_reports', LEGACY_ACTIONS,
                      'ir.actions.client', 'legacy actions', complete=False)
    actions = _by_id(after['community_actions'], 'Community actions')
    action_aliases = _aliases(after['community_action_aliases'], COMMUNITY, tuple('action_' + kind for kind in KINDS),
                              'ir.actions.act_window', 'Community action aliases')
    require(len(actions) == 5 and len({row['res_id'] for row in action_aliases.values()}) == 5,
            'Expected five distinct real Community action records')
    groups = _aliases(after['account_group_aliases'], 'account', GROUPS, 'res.groups', 'accounting roles')
    expected_group_ids = {row['res_id'] for row in groups.values()}
    expected_pairs = {(row['res_id'], group_id) for row in action_aliases.values() for group_id in expected_group_ids}
    actual_pairs = [(row['act_id'], row['gid']) for row in after['community_action_groups']]
    require(len(actual_pairs) == len(expected_pairs) and set(actual_pairs) == expected_pairs,
            'Community action role assignments changed')
    if before['community_action_aliases']:
        _aliases(before['community_action_aliases'], COMMUNITY, tuple('action_' + kind for kind in KINDS),
                 'ir.actions.act_window', 'existing Community action aliases')
        _existing_exact(before['community_action_aliases'], after['community_action_aliases'], 'existing Community action aliases')
        # XML loader write audit can change on an upgrade; all other action
        # values, including context and model, remain the same actual records.
        _existing_exact([_identity_menu(row) for row in before['community_actions']],
                        [_identity_menu(row) for row in after['community_actions']], 'existing Community actions')
    original_menus = _by_id(original_identity['ir_ui_menu'], 'all original menus')
    current_menus = _by_id(current_identity['ir_ui_menu'], 'all current menus')
    source_menus, target_menus = _by_id(before['menus'], 'original launcher menus'), _by_id(after['menus'], 'current launcher menus')
    require(len(source_menus) == len(target_menus) == 5 and
            set(source_menus) == set(target_menus) == {row['res_id'] for row in original_aliases.values()},
            'Original launcher menu IDs changed')
    normalized = deepcopy(current_identity)
    normalized_menus = _by_id(normalized['ir_ui_menu'], 'normalized menus')
    admitted = []
    for name, kind, old_name in zip(MENUS, KINDS, LEGACY_ACTIONS):
        ident = original_aliases[name]['res_id']
        old, now = source_menus[ident], target_menus[ident]
        require(original_menus.get(ident) == _identity_menu(old) and current_menus.get(ident) == _identity_menu(now),
                'Menu snapshots are not bound to the complete identity contracts')
        alias = action_aliases['action_' + kind]
        action = actions.get(alias['res_id'])
        require(action is not None and action.get('type') == 'ir.actions.act_window'
                and action.get('res_model') == 'step.treasury.report'
                and action.get('view_mode') == 'form' and action.get('target') == 'current',
                'Unexpected real Community action model/type/view/target')
        try:
            context = ast.literal_eval(action['context'])
        except (KeyError, ValueError, SyntaxError, TypeError) as error:
            raise AssertionError('Invalid Community action literal context') from error
        require(context == {'default_kind': kind}, 'Unexpected Community action report kind/context')
        require(action.get('domain') in (None, False, '[]'), 'Unexpected Community action domain')
        expected = 'ir.actions.act_window,%s' % action['id']
        if old['action'] != expected:
            native = legacy.get(old_name)
            require(native is not None and old['action'] == 'ir.actions.client,%s' % native['res_id']
                    and native['res_id'] in _by_id(before['global_client_actions'], 'original global actions'),
                    'Original menu does not have its exact approved former action')
        require(now['action'] == expected, 'Launcher does not target its exact Community action')
        require(_identity_menu(dict(now, action=old['action'])) == _identity_menu(old),
                'An original launcher field other than action changed')
        normalized_menus[ident]['action'] = old['action']
        admitted.append({'menu_xmlid': CORE + '.' + name, 'menu_id': ident,
                         'before_action': old['action'], 'after_action': now['action'],
                         'community_action_xmlid': COMMUNITY + '.action_' + kind,
                         'original_xmlid_id': original_aliases[name]['id'],
                         'original_noupdate': original_aliases[name]['noupdate'],
                         'action_changed': old['action'] != now['action']})
    for ident, row in original_menus.items():
        require(normalized_menus.get(ident) == row, 'An unrelated original menu identity changed')
    require(all(row in current_identity['ir_ui_menu_group_rel'] for row in original_identity['ir_ui_menu_group_rel'])
            and all(row in original_identity['ir_ui_menu_group_rel'] for row in current_identity['ir_ui_menu_group_rel']
                    if row.get('menu_id') in original_menus), 'Original menu role relations changed')
    return ({'schema': 1, 'approved_menu_actions': admitted,
             'original_xmlids_exact': True, 'all_original_menus_other_fields_exact': True,
             **client_action_audit, 'normalized_properties': ['ir_ui_menu.action'],
             'read_only': True, 'database_writes': False, 'source': source}, normalized)
