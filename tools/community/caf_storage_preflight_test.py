"""Synthetic metadata tests: no database, business records, CAFs or keys."""
import copy
import unittest
from unittest.mock import patch

import caf_storage_preflight as gate


def reference():
    """Explicit synthetic identity, deliberately unrelated to production IDs."""
    sections = {name: [] for name in gate.SQL}
    sections['transaction'] = [{'read_only': 'on'}]
    sections['models'] = [{'id': 7, 'model': gate.MODEL, 'state': 'base'}]
    sections['fields'] = [{'id': index + 10, 'name': name, 'model': gate.MODEL,
        'ttype': contract[0], 'relation': contract[1], 'store': contract[2]}
        for index, (name, contract) in enumerate(gate.FIELDS.items())]
    types = {'integer': 'integer', 'char': 'character varying', 'selection': 'character varying',
             'many2one': 'integer', 'date': 'date', 'datetime': 'timestamp without time zone'}
    sections['columns'] = [{'column_name': name, 'data_type': types[contract[0]],
                           'is_nullable': 'NO' if name == 'id' else 'YES'}
        for name, contract in gate.FIELDS.items() if name not in ('caf_file', 'display_name')]
    sections['selections'] = [{'id': 501, 'field': 'status', 'value': 'in_use'},
                               {'id': 502, 'field': 'status', 'value': 'spent'}]
    sections['constraints'] = [{'contype': 'u', 'definition': 'UNIQUE (filename)'},
                               {'contype': 'p', 'definition': 'PRIMARY KEY (id)'}]
    sections['relations'] = [{'definition': 'FOREIGN KEY (' + name + ') REFERENCES ' + target + '(id) ON DELETE SET NULL'}
        for name, target in (('company_id', 'res_company'), ('create_uid', 'res_users'),
                            ('write_uid', 'res_users'), ('l10n_latam_document_type_id', 'l10n_latam_document_type'))]
    sections['inverse_fields'] = [{'model': 'l10n_latam.document.type', 'name': 'l10n_cl_dte_caf_ids',
                                  'relation_field': 'l10n_latam_document_type_id'}]
    sections['xmlids'] = [dict(module='l10n_cl_edi', name='model_l10n_cl_dte_caf', model='ir.model', res_id=7)]
    for field in sections['fields']:
        sections['xmlids'].append(dict(module='l10n_cl_edi',
            name='field_l10n_cl_dte_caf__' + field['name'], model='ir.model.fields', res_id=field['id']))
    for selection in sections['selections']:
        sections['xmlids'].append(dict(module='l10n_cl_edi',
            name='selection__l10n_cl_dte_caf__status__' + selection['value'],
            model='ir.model.fields.selection', res_id=selection['id']))
    sections['group_aliases'] = []
    for index, (owner, group) in enumerate((('l10n_cl_edi', 'account'), ('l10n_cl_edi_stock', 'stock'))):
        sections['xmlids'].append(dict(module=owner, name='access_dte_caf_manager',
                                       model='ir.model.access', res_id=100 + index))
        sections['acl'].append(dict(id=100 + index, group_id=200 + index, active=True,
            perm_read=True, perm_write=True, perm_create=True, perm_unlink=True))
        sections['group_aliases'].append(dict(module=group, name='group_' + group + '_manager', res_id=200 + index))
    sections['rules'] = [{'id': 300, 'global': True, 'active': True, 'groups': [],
        'domain_force': "[('company_id', 'in', company_ids + [False])]",
        'perm_read': True, 'perm_write': True, 'perm_create': True, 'perm_unlink': True}]
    sections['caf_rows'] = [dict(records=0, missing_company=0, missing_document_type=0,
                                 invalid_ranges=0, metadata_hash='synthetic-empty')]
    sections['attachments'] = [dict(records=0, public=0, orphan=0, metadata_hash='synthetic-empty')]
    sections['id_counter'] = [dict(last_value=1, is_called=False)]
    return sections


class CAFStoragePreflightCase(unittest.TestCase):
    def assert_rejected(self, sections, error):
        result = gate.assess(sections)
        self.assertFalse(result['metadata_contract_valid'])
        self.assertIn(error, result['errors'])
        self.assertFalse(result['adoption_ready'])

    def test_complete_metadata_is_still_not_permission_to_adopt(self):
        result = gate.assess(reference())
        self.assertTrue(result['metadata_contract_valid'], result['errors'])
        self.assertFalse(result['adoption_ready'])
        self.assertFalse(result['folio_allocation_ready'])
        self.assertFalse(result['payload_read'])
        self.assertIn('no-real-caf-record-for-history-acceptance', result['blockers'])

    def test_read_only_snapshot_is_required(self):
        sections = reference(); sections['transaction'] = [{'read_only': 'off'}]
        self.assert_rejected(sections, 'transaction-not-read-only')

    def test_original_model_and_xmlid_must_be_identical(self):
        sections = reference(); sections['xmlids'][0]['res_id'] = 8
        self.assert_rejected(sections, 'model-xmlid')
        sections = reference(); sections['models'].append(dict(id=8, model=gate.MODEL))
        self.assert_rejected(sections, 'model-identity')

    def test_missing_or_retyped_master_relation_is_blocked(self):
        sections = reference()
        field = next(row for row in sections['fields'] if row['name'] == 'company_id')
        field['ttype'] = 'char'; field['relation'] = None
        self.assert_rejected(sections, 'field-contract:company_id')

    def test_field_and_selection_aliases_cannot_change_identity(self):
        sections = reference()
        alias = next(row for row in sections['xmlids'] if row['name'] == 'field_l10n_cl_dte_caf__company_id')
        alias['res_id'] += 1
        self.assert_rejected(sections, 'field-xmlid:company_id')
        sections = reference()
        sections['xmlids'] = [row for row in sections['xmlids'] if row['name'] != 'selection__l10n_cl_dte_caf__status__spent']
        self.assert_rejected(sections, 'selection-xmlid:spent')

    def test_parallel_counter_and_binary_column_are_rejected(self):
        sections = reference(); sections['fields'].append(dict(name='next_folio', ttype='integer', store=True))
        self.assert_rejected(sections, 'field-set')
        sections = reference(); sections['columns'].append(dict(column_name='caf_file', data_type='bytea', is_nullable='YES'))
        self.assert_rejected(sections, 'physical-column-set')

    def test_physical_type_or_nullability_cannot_drift(self):
        sections = reference(); sections['columns'][0]['is_nullable'] = 'YES'
        self.assert_rejected(sections, 'physical-column-contract:id')
        sections = reference(); sections['columns'][0]['data_type'] = 'text'
        self.assert_rejected(sections, 'physical-column-contract:id')

    def test_status_and_original_filename_constraint_are_preserved(self):
        sections = reference(); sections['selections'][0]['value'] = 'draft'
        self.assert_rejected(sections, 'status-selection')
        sections = reference(); sections['constraints'] = []
        self.assert_rejected(sections, 'filename-unique')

    def test_foreign_keys_and_delete_policy_are_preserved(self):
        sections = reference(); sections['relations'][0]['definition'] = sections['relations'][0]['definition'].replace('SET NULL', 'CASCADE')
        self.assert_rejected(sections, 'foreign-key-contract')

    def test_manager_roles_and_acl_cannot_expand(self):
        sections = reference(); sections['acl'][0]['group_id'] = None
        self.assert_rejected(sections, 'acl-contract:l10n_cl_edi')
        sections = reference(); sections['acl'].append(dict(id=102, perm_read=True))
        self.assert_rejected(sections, 'acl-set')

    def test_global_company_rule_cannot_be_weakened(self):
        sections = reference(); sections['rules'][0]['domain_force'] = '[]'
        self.assert_rejected(sections, 'company-rule-contract')
        sections = reference(); sections['rules'][0]['groups'] = [200]
        self.assert_rejected(sections, 'company-rule-contract')

    def test_public_or_orphan_attachments_are_reported(self):
        for field in ('public', 'orphan'):
            sections = reference(); sections['attachments'][0][field] = 1
            self.assert_rejected(sections, 'attachment-exposure-or-orphan')

    def test_real_record_counts_do_not_prove_payload_or_allocator(self):
        sections = reference(); sections['caf_rows'][0]['records'] = 1
        result = gate.assess(sections)
        self.assertTrue(result['metadata_contract_valid'])
        self.assertNotIn('no-real-caf-record-for-history-acceptance', result['blockers'])
        self.assertIn('native-folio-allocation-and-concurrency-not-proven', result['blockers'])
        self.assertIn('payload-and-key-validation-not-performed', result['blockers'])
        self.assertFalse(result['adoption_ready'])

    def test_exact_comparison_detects_original_counter_consumption(self):
        before = {'sections': reference()}; after = copy.deepcopy(before)
        self.assertTrue(gate.compare(before, after)['preserved'])
        after['sections']['id_counter'][0]['is_called'] = True
        result = gate.compare(before, after)
        self.assertFalse(result['preserved'])
        self.assertEqual(result['changed_sections'], ['id_counter'])

    def test_exact_comparison_detects_ids_acls_and_storage_changes(self):
        before = {'sections': reference()}
        for section, key in (('fields', 'id'), ('acl', 'group_id'), ('attachments', 'metadata_hash')):
            after = copy.deepcopy(before); after['sections'][section][0][key] = 'changed'
            result = gate.compare(before, after)
            self.assertFalse(result['preserved'])
            self.assertEqual(result['changed_sections'], [section])

    def test_sql_has_no_payload_export_or_mutating_function(self):
        sql = '\n'.join(gate.SQL.values()).lower()
        for text in ('nextval(', 'setval(', 'caf_file from',
                     'pg_read_file(', 'lo_get(', 'decode(', 'rsask', 'rsapubk'):
            self.assertNotIn(text, sql)
        self.assertNotRegex(sql, r'\b(?:update|delete|insert)\s')
        self.assertIn('a.db_datas is not null', sql)
        self.assertNotIn('a.db_datas,', sql)

    def test_production_names_are_rejected_before_database_access(self):
        for database in ('CERRO_EL_PLOMO', 'SyS', 'karo_consultorias', 'QA_CERROELPLOMO'):
            with (self.subTest(database=database), patch('sys.argv', ['preflight', '--database', database,
                    '--output', '/private/output.json']), patch.object(gate, 'read_metadata') as reader,
                    patch('sys.stderr')):
                with self.assertRaises(SystemExit) as error:
                    gate.main()
                self.assertEqual(error.exception.code, 2)
                reader.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
