"""Typed synthetic defaults only; no database, ORM, conditions or amounts."""
from copy import deepcopy
import unittest

import original_external_references_defaults as defaults
from test_original_external_references import field


def fixture():
    from test_original_external_references import fixture as base
    catalog, registry, _, _ = base()
    for model, table, fields in [('ir.default', 'actual_defaults', [field('field_id', 'many2one', 'ir.model.fields'),
            field('user_id', 'many2one', 'res.users'), field('company_id', 'many2one', 'res.company')]),
            ('ir.model.fields', 'actual_field_metadata', []), ('product.category', 'actual_category',
            [field('property_account_id', 'many2one', 'account.account', company_dependent=True)]),
            ('account.account', 'actual_account', []), ('res.users', 'actual_users', []), ('res.company', 'actual_companies', [])]:
        registry['models'].append(dict(model=model, table=table, fields=fields, abstract=False, auto=True, transient=False, inherits={}))
        catalog['tables'].append(dict(name=table, schema='public', kind='r'))
    catalog['columns'] += [dict(table_name='actual_defaults', name=name, sql_type=kind, not_null=name == 'id')
        for name, kind in [('id', 'integer'), ('field_id', 'integer'), ('user_id', 'integer'), ('company_id', 'integer'),
            ('condition', 'character varying'), ('json_value', 'text')]]
    catalog['keys'].append(dict(table_name='actual_defaults', name='actual_defaults_pkey', columns=['id'], primary_key=True))
    catalog['foreign_keys'].append(dict(name='default_field_fk', source_schema='public', source_table='actual_defaults',
        source_columns=['field_id'], target_schema='public', target_table='actual_field_metadata', target_columns=['id'], validated=True))
    catalog['foreign_keys'] += [dict(name='default_' + name + '_fk', source_schema='public', source_table='actual_defaults',
        source_columns=[name], target_schema='public', target_table=target, target_columns=['id'], validated=True)
        for name, target in (('user_id', 'actual_users'), ('company_id', 'actual_companies'))]
    catalog['fields'].append(dict(id=901, model='product.category', name='property_account_id', ttype='many2one',
        relation='account.account', store=True, company_dependent=True))
    reference = {'observations': catalog, 'scope': {'ir.actions.report': {'ids': [462]}, 'hr.salary.rule': {'ids': [1]}}}
    row = {'owner_pk': {'id': 19, '_physical_table': 'actual_defaults'}, 'field_id': 901, 'user_id': None, 'company_id': None,
        'condition_sha256': 'a' * 64, 'row_sha256': 'b' * 64, 'value_sha256': 'c' * 64,
        'model': 'product.category', 'field_name': 'property_account_id', 'ttype': 'many2one', 'relation': 'account.account',
        'store': True, 'company_dependent': True, 'reference_json': '462'}
    return reference, registry, row


class TypedDefaultCase(unittest.TestCase):
    def test_numbers_bind_to_field_comodel_not_coincident_report_ids(self):
        reference, registry, row = fixture()
        result = defaults.classify([row], reference, registry)[0]
        self.assertEqual(result['targets'], [{'model': 'account.account', 'table': 'actual_account', 'id': 462}])
        self.assertEqual(result['adoption_target_hits'], [])
        self.assertIsNone(result['company_id'])
        self.assertFalse(result['writer_authorized'])
        self.assertNotIn('reference_json', result)
        self.assertEqual(result['condition_sha256'], row['condition_sha256'])

    def test_literal_relational_commands_are_parsed_but_never_applied(self):
        models = {'target.model': {}}
        self.assertEqual(defaults.targets('many2many', '[[6,0,[1,2]],[4,3,0]]', 'target.model', models),
            [('target.model', 1), ('target.model', 2), ('target.model', 3)])
        self.assertEqual(defaults.targets('reference', '"target.model,462"', None, models), [('target.model', 462)])
        for raw in ('true', '-1', '1.0', '2147483648', 'NaN', 'Infinity', '"__import__(\"os\")"'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): defaults.targets('many2one', raw, 'target.model', models)
        for raw in ('[[0,0,{}]]', '[[1,1,{}]]', '[[2,1]]', '[[3,1]]', '[[5]]', '[[4,true]]', '{"ids":[1]}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): defaults.targets('many2many', raw, 'target.model', models)
        with self.assertRaises(ValueError): defaults.targets('reference', '"unregistered.model,1"', None, models)

    def test_unknown_scalar_masked_payload_wrong_metadata_or_duplicate_owner_stays_unresolved(self):
        reference, registry, row = fixture()
        for change in ('scalar', 'masked', 'wrong_model', 'wrong_field', 'wrong_store'):
            altered = deepcopy(row)
            if change == 'scalar': altered.update(ttype='integer', relation=None, reference_json=None)
            elif change == 'masked': altered['reference_json'] = None
            elif change == 'wrong_model': altered['relation'] = 'ir.actions.report'
            elif change == 'wrong_field': altered['field_id'] = 999
            elif change == 'wrong_store': altered['store'] = False
            result = defaults.classify([altered], reference, registry)[0]
            self.assertEqual(result['status'], 'unresolved')
            self.assertFalse(result['writer_authorized'])
        with self.assertRaises(ValueError): defaults.classify([row, row], reference, registry)

    def test_actual_default_storage_fk_and_safe_payload_projection_are_required(self):
        reference, registry, _ = fixture()
        binding = defaults.contract(reference, registry)
        sql = defaults.queries(binding)['defaults']
        self.assertIn('LEFT JOIN ONLY public."actual_field_metadata"', sql)
        self.assertIn('CASE WHEN', sql)
        self.assertIn('ELSE NULL END AS reference_json', sql)
        self.assertIn('condition_sha256', sql)
        self.assertNotIn('d.condition AS', sql)
        self.assertNotIn('eval(', sql)
        for command in ('UPDATE ', 'INSERT ', 'DELETE ', 'CREATE ', 'ALTER ', 'DROP '): self.assertNotIn(command, sql)
        reference['observations']['foreign_keys'].pop()
        with self.assertRaises(ValueError): defaults.contract(reference, registry)


if __name__ == '__main__': unittest.main()
