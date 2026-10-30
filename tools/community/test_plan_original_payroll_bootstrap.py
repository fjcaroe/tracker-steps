import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import plan_original_payroll_bootstrap as plan


def fixture():
    counts = (4, 5, 6, 71, 34)
    capsule = dict(schema=1, read_only=True, unresolved_company_properties=[], relations=[],
        **{name: False for name in ('orm_loaded', 'rules_evaluated', 'historical_payroll_read',
           'engine_converted', 'financial_certified', 'import_authorized_by_capsule')})
    capsule['tables'] = {}
    for (table, model), count in zip(plan.gate.TABLES.items(), counts):
        rows = [json.dumps({'id': value, 'source_value': None}) for value in range(1, count + 1)]
        capsule['tables'][table] = {'model': model, 'row_count': count, 'rows_json': rows,
            'rows_sha256': hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
    aliases = [dict(id=41750 + i, module=module, name=name, model='hr.payroll.structure.type',
                    res_id=i + 1, noupdate=True) for i, (module, name) in enumerate(plan.TYPE_ALIASES)]
    aliases += [dict(id=50000 + i, module='hr_payroll', name='rule_' + str(i),
                    model='hr.salary.rule', res_id=i, noupdate=False) for i in range(1, 72)]
    aliases += [dict(id=51000 + i, module='l10n_cl_simpledigital_payroll', name='category_' + str(i),
                    model='hr.salary.rule.category', res_id=i, noupdate=True) for i in range(1, 14)]
    original = copy.deepcopy(aliases)
    aliases += [dict(id=221718 + i, module=module, name=name, model='hr.salary.rule',
                    res_id=i + 1, noupdate=True) for i, (module, name) in enumerate(sorted(plan.REFERENCE_ALIASES))]
    report_alias = dict(id=51853, module='hr_payroll', name='action_report_payslip',
                        model='ir.actions.report', res_id=462, noupdate=False)
    capsule['xmlids'] = aliases
    identity = {'original_xmlids': original + [report_alias],
        'ir_model': [{'id': 600, 'model': 'hr.payslip', 'transient': False}],
        'ir_model_fields': [{'id': 900, 'model': 'hr.payslip', 'name': 'number'}],
        'ir_model_fields_selection': [{'id': 901, 'field_id': 900, 'value': 'draft'}]}
    preflight = {'source_external_metadata': {'external:ir_act_report_xml': [
        {'id': 462, 'model': 'hr.payslip', 'report_name': 'hr_payroll.report_payslip_lang',
         'report_type': 'qweb-pdf', 'binding_model_id': 600}]}}
    return capsule, identity, preflight


class BootstrapIdentityPlanCase(unittest.TestCase):
    def contracts(self):
        capsule, identity, preflight = fixture()
        return capsule, plan.original_aliases(capsule, identity), plan.source_report(preflight, identity)

    def empty(self):
        return {'transaction': [{'mode': 'on'}],
            'modules': [{'name': 'base', 'state': 'installed', 'license': 'LGPL-3', 'demo': False}],
            'metadata_occupants': [], 'action_462': [], 'action_aliases': [],
            'binding_models': [], 'tables': [], 'sequences': []}

    def test_classifies_88_original_aliases_without_borrowing_reference_metadata_pks(self):
        capsule, identity, _ = fixture()
        self.assertEqual(len(plan.original_aliases(capsule, identity)), 88)
        identity['original_xmlids'].append(capsule['xmlids'][-1])
        with self.assertRaisesRegex(ValueError, 'reference-alias-already-in-original'):
            plan.original_aliases(capsule, identity)

    def test_false_noupdate_and_metadata_primary_keys_are_exact_contracts(self):
        for field, value in [('noupdate', False), ('id', 88), ('res_id', 2), ('model', 'other.model')]:
            with self.subTest(field=field):
                capsule, identity, _ = fixture()
                identity['original_xmlids'][0][field] = value
                with self.assertRaisesRegex(ValueError, 'original-alias-identity-or-noupdate-drift'):
                    plan.original_aliases(capsule, identity)

    def test_base_only_vacancy_does_not_admit_report_without_binding_model_and_renderer(self):
        args = self.contracts()
        result = plan.assess(*args, self.empty())
        self.assertTrue(result['original_action_id_vacant'])
        self.assertFalse(result['numeric_identity_checkpoint_clear'])
        self.assertIn('original-binding-model-pk-not-exact-real-payslip-model', result['blockers'])
        self.assertIn('real-community-renderer-not-observed-in-registry', result['blockers'])
        self.assertFalse(result['reservation_authorized'])

    def test_clear_numeric_space_still_never_authorizes_values_or_import(self):
        args = self.contracts()
        observed = self.empty()
        observed['binding_models'] = [{'id': 600, 'model': 'hr.payslip'}]
        result = plan.assess(*args, observed, runtime_registry={'real_community_renderer': True})
        self.assertTrue(result['numeric_identity_checkpoint_clear'])
        self.assertFalse(result['import_authorized'])
        self.assertFalse(result['references_and_original_values_adopted'])

    def test_same_canonical_alias_with_another_metadata_pk_or_unrelated_occupant_blocks(self):
        capsule, aliases, report = self.contracts()
        for variant in ('different-pk', 'unrelated-pk', 'flag'):
            with self.subTest(variant=variant):
                observed = self.empty()
                row = copy.deepcopy(aliases[0])
                if variant == 'different-pk': row['id'] += 100
                elif variant == 'unrelated-pk': row.update(module='hr_expense', name='product_meal', model='product.product')
                else: row['noupdate'] = False
                observed['metadata_occupants'] = [row]
                result = plan.assess(capsule, aliases, report, observed)
                self.assertIn('original-metadata-pk-or-name-occupied', result['blockers'])

    def test_action_and_binding_conflicts_cannot_be_relabelled_as_renderer_compatibility(self):
        args = self.contracts()
        observed = self.empty()
        observed['action_462'] = [{'id': 462, 'type': 'ir.actions.act_window', 'physical_table': 'ir_act_window'}]
        observed['action_aliases'] = [{'id': 43553, 'module': 'hr_holidays', 'name': 'hr_leave_allocation_action_all'}]
        observed['binding_models'] = [{'id': 600, 'model': 'other.model'}, {'id': 645, 'model': 'hr.payslip'}]
        result = plan.assess(*args, observed, runtime_registry={'real_community_renderer': True})
        self.assertIn('original-action-462-already-occupied', result['blockers'])
        self.assertIn('original-binding-model-pk-not-exact-real-payslip-model', result['blockers'])
        self.assertFalse(result['renumbering_authorized'])

    def test_source_binding_must_resolve_to_real_nontransient_original_model(self):
        for change in ('id', 'model', 'transient'):
            with self.subTest(change=change):
                _, identity, preflight = fixture()
                identity['ir_model'][0][change] = {'id': 601, 'model': 'different.model', 'transient': True}[change]
                with self.assertRaisesRegex(ValueError, 'original-binding-model-identity-not-proven'):
                    plan.source_report(preflight, identity)

    def test_seed_demo_enterprise_and_pending_states_remain_blockers(self):
        args = self.contracts()
        observed = self.empty()
        observed['modules'].append({'name': 'native', 'state': 'to remove', 'license': 'OEEL-1', 'demo': True})
        observed['count:hr_salary_rule'] = [{'rows': 1}]
        observed['count:hr_payroll_structure_type'] = [{'rows': 5}]
        result = plan.assess(*args, observed)
        for code in ('enterprise-module-in-cold-target', 'demo-module-in-cold-target',
                     'module-graph-not-quiescent', 'salary-seeds-or-adopted-records-already-present',
                     'noncanonical-or-extra-type-seeds-present'):
            self.assertIn(code, result['blockers'])

    def test_queries_are_select_only_without_sequences_allocation_or_business_amounts(self):
        capsule, aliases, report = self.contracts()
        queries = plan.checkpoint_queries(aliases, report)
        queries.update(plan.master_queries([{'tablename': name} for name in plan.gate.TABLES], capsule))
        for query in queries.values():
            self.assertTrue(query.startswith('SELECT '))
            self.assertNotIn('nextval', query.lower())
            self.assertNotIn('setval', query.lower())
            self.assertNotIn('hr_payslip_input', query.replace('hr_payslip_input_type', ''))
            self.assertNotIn('amount', query)
        self.assertIn('md5(to_jsonb(t)::text)', queries['masters:hr_salary_rule'])

    def test_dependency_minimum_honors_depth_names_data_order_and_free_sources_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, depends in [('base', []), ('b', ['base']), ('a', ['base']), ('payroll', ['b', 'a'])]:
                folder = root / name
                folder.mkdir()
                (folder / '__manifest__.py').write_text(repr({'license': 'LGPL-3', 'depends': depends,
                    'data': ['second.xml', 'first.xml']}))
                for file in ('second.xml', 'first.xml'):
                    (folder / file).write_text('<odoo><record id="action" model="ir.actions.report"><field name="name">PRIVATE TEXT</field></record></odoo>')
            result = plan.dependency_minimum([root], ['payroll'])
            self.assertEqual([row['module'] for row in result['minimum_order']], ['base', 'a', 'b', 'payroll'])
            self.assertEqual([row['file'] for row in result['minimum_order'][-1]['data']], ['second.xml', 'first.xml'])
            self.assertNotIn('PRIVATE TEXT', json.dumps(result))
            self.assertFalse(result['actual_auto_install_graph_proven'])
            self.assertFalse(result['numeric_allocations_predicted'])
            (root / 'payroll/__manifest__.py').write_text(repr({'license': 'OEEL-1', 'depends': ['base']}))
            with self.assertRaisesRegex(ValueError, 'nonfree-module-source-not-readable'):
                plan.dependency_minimum([root], ['payroll'])


if __name__ == '__main__':
    unittest.main()
