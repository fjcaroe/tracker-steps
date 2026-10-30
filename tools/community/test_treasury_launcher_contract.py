"""Synthetic, offline negatives for the exact five-menu admission policy."""
from copy import deepcopy
import json
import unittest

import treasury_launcher_contract as contract


def fixture():
    aliases = [{'id': 1000 + index, 'module': contract.CORE, 'name': name,
                'model': 'ir.ui.menu', 'res_id': 100 + index, 'noupdate': bool(index % 2),
                'create_uid': 1, 'create_date': 'original', 'write_uid': 1, 'write_date': 'original'}
               for index, name in enumerate(contract.MENUS)]
    menus = [{'id': 100 + index, 'name': {'en_US': name, 'es_CL': 'Original'},
              'parent_id': 80, 'sequence': 10 + index, 'active': index != 2,
              'action': 'ir.actions.client,%s' % (200 + index), 'web_icon': None,
              'create_uid': 1, 'create_date': 'original', 'write_uid': 1, 'write_date': 'original'}
             for index, name in enumerate(contract.MENUS)]
    legacy = [{'id': 2000 + index, 'module': 'account_reports', 'name': name,
               'model': 'ir.actions.client', 'res_id': 200 + index, 'noupdate': False}
              for index, name in enumerate(contract.LEGACY_ACTIONS)]
    group_aliases = [{'id': 3000 + index, 'module': 'account', 'name': name,
                      'model': 'res.groups', 'res_id': 30 + index, 'noupdate': True}
                     for index, name in enumerate(contract.GROUPS)]
    stamp_aliases = [{'id': 11000 + index, 'module': module, 'name': name,
                     'model': 'ir.actions.client', 'res_id': 700 + index, 'noupdate': bool(index % 2)}
                    for index, (module, name) in enumerate(contract.CLIENT_TIMESTAMP_XMLIDS)]
    before = {'schema': 1, 'menu_aliases': aliases, 'menus': menus,
              'menu_groups': [{'menu_id': 100, 'gid': 42}],
              'global_client_actions': [{'id': 200 + index, 'tag': 'account_report',
                  'params': {'report_id': index + 1}, 'name': {'en_US': 'Original native action'},
                  'write_uid': 1, 'write_date': 'original'} for index in range(5)],
              'legacy_action_aliases': legacy, 'community_action_aliases': [],
              'community_actions': [], 'community_action_groups': [], 'account_group_aliases': group_aliases}
    before['global_client_actions'] += [{'id': 700 + index, 'tag': 'owned_dashboard', 'params': None,
        'name': {'en_US': name}, 'write_uid': 1, 'write_date': '2026-10-01T00:00:00'}
        for index, (module, name) in enumerate(contract.CLIENT_TIMESTAMP_XMLIDS)]
    after = deepcopy(before)
    after['community_action_aliases'] = [
        {'id': 4000 + index, 'module': contract.COMMUNITY, 'name': 'action_' + kind,
         'model': 'ir.actions.act_window', 'res_id': 500 + index, 'noupdate': False}
        for index, kind in enumerate(contract.KINDS)]
    after['community_actions'] = [{'id': 500 + index, 'type': 'ir.actions.act_window',
        'res_model': 'step.treasury.report', 'view_mode': 'form', 'target': 'current',
        'context': repr({'default_kind': kind}), 'domain': '[]',
        'name': {'en_US': 'Actual Community action'}} for index, kind in enumerate(contract.KINDS)]
    after['community_action_groups'] = [{'act_id': 500 + index, 'gid': group_id}
        for index in range(5) for group_id in (30, 31)]
    for index, menu in enumerate(after['menus']):
        menu.update(action='ir.actions.act_window,%s' % (500 + index), write_uid=1, write_date='upgrade')
    project = lambda rows: [{key: row[key] for key in ('id', 'module', 'name', 'model', 'res_id', 'noupdate')} for row in rows]
    original = {'ir_ui_menu': [contract._identity_menu(row) for row in before['menus']]
        + [{'id': 999, 'name': {'en_US': 'Unrelated menu'}, 'action': 'ir.actions.client,777'}],
        'original_xmlids': project(aliases + legacy + group_aliases + stamp_aliases)
            + [{'id': 9999, 'module': 'other_app', 'name': 'original', 'model': 'ir.ui.view', 'res_id': 8, 'noupdate': False}],
        'ir_ui_menu_group_rel': deepcopy(before['menu_groups']),
        'ir_model_fields': [{'id': 6, 'model': 'other.model', 'name': 'field', 'ttype': 'char'}],
        'ir_rule': [{'id': 9, 'domain_force': "[('company_id', 'in', company_ids)]"}]}
    current = deepcopy(original)
    current['ir_ui_menu'][:5] = [contract._identity_menu(row) for row in after['menus']]
    current['original_xmlids'] += project(after['community_action_aliases'])
    return original, current, before, after


class TreasuryLauncherContractCase(unittest.TestCase):
    def test_exact_five_changes_only_and_inputs_are_immutable(self):
        values = fixture()
        untouched = deepcopy(values)
        audit, normalized = contract.verify(*values)
        self.assertEqual(values, untouched)
        self.assertEqual(normalized['ir_ui_menu'], values[0]['ir_ui_menu'])
        self.assertEqual(normalized['original_xmlids'], values[1]['original_xmlids'])
        self.assertEqual(sum(row['action_changed'] for row in audit['approved_menu_actions']), 5)
        self.assertEqual(audit['normalized_properties'], ['ir_ui_menu.action'])
        self.assertTrue(audit['original_global_client_actions_exact'])
        # Already-converted baselines are exact/idempotent; no false legacy
        # action alias is required to license an unchanged target.
        original, current, before, after = fixture()
        original = deepcopy(current)
        before = deepcopy(after)
        audit, normalized = contract.verify(original, current, before, after)
        self.assertFalse(any(row['action_changed'] for row in audit['approved_menu_actions']))
        self.assertEqual(normalized, current)

    def test_menu_fields_groups_other_menu_and_missing_rows_cannot_change(self):
        for field, value in [('name', {'en_US': 'Changed'}), ('parent_id', 1), ('sequence', 800),
                             ('active', True), ('web_icon', 'new,icon')]:
            values = fixture()
            values[3]['menus'][2][field] = value
            values[1]['ir_ui_menu'][2][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                contract.verify(*values)
        for edit in ('unrelated', 'removed', 'role', 'extra_role'):
            values = fixture()
            if edit == 'unrelated': values[1]['ir_ui_menu'][-1]['action'] = 'ir.actions.client,888'
            elif edit == 'removed': values[1]['ir_ui_menu'].pop()
            elif edit == 'role': values[1]['ir_ui_menu_group_rel'][0]['gid'] = 1
            else: values[1]['ir_ui_menu_group_rel'].append({'menu_id': 100, 'gid': 1})
            with self.subTest(edit=edit), self.assertRaises(AssertionError):
                contract.verify(*values)

    def test_original_xmlid_flags_models_rows_and_global_actions_remain_exact(self):
        for field, value in [('noupdate', True), ('model', 'ir.actions.client'), ('res_id', 999),
                             ('module', 'other_app')]:
            values = fixture()
            values[3]['menu_aliases'][0][field] = value
            values[1]['original_xmlids'][0][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                contract.verify(*values)
        for edit in ('other_xmlid', 'tag', 'params', 'action_deleted', 'alias_retarget'):
            values = fixture()
            if edit == 'other_xmlid': next(row for row in values[1]['original_xmlids'] if row['id'] == 9999)['noupdate'] = True
            elif edit == 'tag': values[3]['global_client_actions'][0]['tag'] = 'other_widget'
            elif edit == 'params': values[3]['global_client_actions'][0]['params'] = {'report_id': 999}
            elif edit == 'action_deleted': values[3]['global_client_actions'].pop()
            else: values[3]['legacy_action_aliases'][0]['res_id'] = 201
            with self.subTest(edit=edit), self.assertRaises(AssertionError):
                contract.verify(*values)

    def test_target_context_model_domain_role_and_duplicate_identity_are_rejected(self):
        for field, value in [('res_model', 'account.move'), ('view_mode', 'list'), ('target', 'new'),
                             ('context', "{'default_kind': 'payable'}"), ('domain', "[('id','=',1)]"),
                             ('context', "__import__('os').system('false')")]:
            values = fixture()
            values[3]['community_actions'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(AssertionError):
                contract.verify(*values)
        for edit in ('wrong_target', 'role', 'duplicate', 'counterfeit_original'):
            values = fixture()
            if edit == 'wrong_target':
                values[3]['menus'][0]['action'] = values[1]['ir_ui_menu'][0]['action'] = 'ir.actions.act_window,501'
            elif edit == 'role': values[3]['community_action_groups'][0]['gid'] = 99
            elif edit == 'duplicate': values[3]['community_action_aliases'].append(deepcopy(values[3]['community_action_aliases'][0]))
            else:
                values[2]['menus'][0]['action'] = values[0]['ir_ui_menu'][0]['action'] = 'ir.actions.client,201'
            with self.subTest(edit=edit), self.assertRaises(AssertionError):
                contract.verify(*values)

    def test_unrelated_field_and_rule_differences_are_never_normalized(self):
        values = fixture()
        values[1]['ir_model_fields'][0]['ttype'] = 'text'
        values[1]['ir_rule'][0]['domain_force'] = '[]'
        unused_audit, normalized = contract.verify(*values)
        self.assertEqual(normalized['ir_model_fields'], values[1]['ir_model_fields'])
        self.assertEqual(normalized['ir_rule'], values[1]['ir_rule'])
        self.assertNotEqual(normalized['ir_model_fields'], values[0]['ir_model_fields'])
        self.assertNotEqual(normalized['ir_rule'], values[0]['ir_rule'])
        # The canonical later equality still rejects these changes. This policy
        # is not a bypass for any other metadata table or HR admission policy.

    def test_only_seven_alias_bound_write_dates_are_admitted_and_never_menu_normalized(self):
        values = fixture()
        # Remap every synthetic allowed target to prove that actual numeric
        # action IDs are derived, rather than guessed from a source database.
        mapping = {700 + index: 1700 + index for index in range(7)}
        for identity in values[:2]:
            for row in identity['original_xmlids']:
                if row.get('model') == 'ir.actions.client' and row.get('res_id') in mapping:
                    row['res_id'] = mapping[row['res_id']]
        for snapshot in values[2:]:
            for row in snapshot['global_client_actions']:
                if row['id'] in mapping:
                    row['id'] = mapping[row['id']]
        for row in values[3]['global_client_actions']:
            if row['id'] in mapping.values():
                row['write_date'] = '2026-10-30T03:00:00'
        untouched = deepcopy(values)
        audit, normalized = contract.verify(*values)
        self.assertFalse(audit['original_global_client_actions_exact'])
        self.assertTrue(audit['original_global_client_actions_functional_exact'])
        self.assertEqual(len(audit['approved_client_action_write_date_changes']), 7)
        self.assertEqual({row['action_id'] for row in audit['approved_client_action_write_date_changes']}, set(mapping.values()))
        self.assertTrue(all(row['all_other_raw_columns_exact'] for row in audit['approved_client_action_write_date_changes']))
        self.assertEqual(audit['normalized_properties'], ['ir_ui_menu.action'])
        self.assertEqual(normalized['ir_ui_menu'], values[0]['ir_ui_menu'])
        self.assertEqual(values, untouched)

    def test_timestamp_admission_never_allows_uid_value_alias_flag_extra_or_ee_changes(self):
        for edit in ('write_uid', 'tag', 'params', 'alias', 'flag', 'extra_action', 'ee_timestamp', 'ee_shared_owner'):
            values = fixture()
            target = next(row for row in values[3]['global_client_actions'] if row['id'] == 700)
            target['write_date'] = '2026-10-30T03:00:00'
            alias = next(row for row in values[1]['original_xmlids'] if row.get('res_id') == 700)
            if edit == 'write_uid': target['write_uid'] = 2
            elif edit == 'tag': target['tag'] = 'different_dashboard'
            elif edit == 'params': target['params'] = {'new': 'functional value'}
            elif edit == 'alias': alias['res_id'] = 701
            elif edit == 'flag': alias['noupdate'] = not alias['noupdate']
            elif edit == 'extra_action': values[3]['global_client_actions'].append(dict(target, id=99999))
            elif edit == 'ee_timestamp': values[3]['global_client_actions'][0]['write_date'] = '2026-10-30T03:00:00'
            else:
                # Even a second original owner cannot exempt an EE report.
                for identity in values[:2]:
                    next(row for row in identity['original_xmlids'] if row['id'] == alias['id'])['res_id'] = 200
            with self.subTest(edit=edit), self.assertRaises(AssertionError):
                contract.verify(*values)

    def test_snapshot_is_select_only_and_source_mapping_is_sealed(self):
        captured = []
        def sql(database, query):
            captured.append((database, query))
            return json.dumps({key: [] for key in ('menu_aliases', 'menus', 'menu_groups',
                'global_client_actions', 'legacy_action_aliases', 'community_action_aliases',
                'community_actions', 'community_action_groups', 'account_group_aliases')})
        result = contract.snapshot(sql, 'PRIVATE_SYNTHETIC')
        self.assertEqual(result['schema'], 1)
        self.assertEqual(len(captured), 1)
        self.assertTrue(captured[0][1].startswith('SELECT '))
        self.assertNotIn('account_move', captured[0][1])
        for forbidden in ('UPDATE ', 'DELETE ', 'INSERT ', 'ALTER ', 'CREATE ', 'DROP '):
            self.assertNotIn(forbidden, captured[0][1])
        source = contract.source_contract()
        self.assertEqual(source['menu_kind_mapping'], dict(zip(contract.MENUS, contract.KINDS)))
        self.assertEqual(len(source['files_sha256']), 5)


if __name__ == '__main__':
    unittest.main()
