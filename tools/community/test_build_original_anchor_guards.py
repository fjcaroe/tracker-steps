import copy
import unittest

import build_original_anchor_guards as guard
from test_plan_original_payroll_bootstrap import fixture


class AnchorGuardsCase(unittest.TestCase):
    def specs(self):
        capsule, original, preflight = fixture()
        return guard.guard_specs(capsule, original, copy.deepcopy(original), preflight)

    def test_exact_original_flags_and_all_original_master_columns_are_guarded(self):
        specs = self.specs()
        metadata = next(row for row in specs if row['table'] == 'ir_model_data')
        self.assertIn('noupdate', metadata['columns'])
        self.assertIn(41750, metadata['ids'])
        masters = next(row for row in specs if row['table'] == 'hr_salary_rule')
        self.assertEqual(masters['columns'], ['id', 'source_value'])
        self.assertEqual(len(masters['ids']), 71)
        self.assertNotIn('new_nullable_oca_column', masters['columns'])

    def test_anchor_alias_retarget_noupdate_or_pk_drift_rejects_before_sql_generation(self):
        for name, value in [('id', 90000), ('noupdate', False), ('res_id', 3), ('model', 'other.model')]:
            with self.subTest(name=name):
                capsule, original, preflight = fixture()
                anchor = copy.deepcopy(original)
                anchor['original_xmlids'][0][name] = value
                with self.assertRaisesRegex(ValueError, 'anchor-original-alias-identity-drift'):
                    guard.guard_specs(capsule, original, anchor, preflight)

    def test_wrong_report_alias_or_binding_model_is_not_an_admissible_anchor(self):
        capsule, original, preflight = fixture()
        for variant in ('report', 'binding'):
            anchor = copy.deepcopy(original)
            if variant == 'report': anchor['original_xmlids'][-1]['res_id'] = 463
            else: anchor['ir_model'][0]['id'] = 645
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                guard.guard_specs(capsule, original, anchor, preflight)

    def test_sql_is_atomic_private_guard_only_with_no_runtime_or_sequence_bypass(self):
        specs = self.specs()
        sql = guard.render_sql('MANAGEMENT_QA_CERRO_PAYROLL_API_ADOPTION_SANDBOX_TEST', specs)
        self.assertTrue(sql.startswith('BEGIN;'))
        self.assertTrue(sql.endswith('COMMIT;\n'))
        self.assertIn("current_database() <> 'MANAGEMENT_QA_CERRO_PAYROLL_API_ADOPTION_SANDBOX_TEST'", sql)
        self.assertEqual(sql.count('BEFORE DELETE OR UPDATE ON'), len(specs))
        self.assertEqual(sql.count('BEFORE TRUNCATE ON'), len(specs))
        self.assertIn("ERRCODE='23514'", sql)
        self.assertIn("state='to remove'", sql)
        self.assertIn('IS DISTINCT FROM', sql)
        for forbidden in ('setval(', 'nextval(', 'UPDATE ir_model_data', 'DELETE FROM',
                          'DISABLE TRIGGER', 'CREATE OR REPLACE', 'loaded_xmlids'):
            self.assertNotIn(forbidden, sql)

    def test_report_and_role_edges_are_guarded_without_rebinding_ids(self):
        specs = self.specs()
        report = next(row for row in specs if row['table'] == 'ir_act_report_xml')
        role = next(row for row in specs if row['table'] == 'res_groups_report_rel')
        self.assertEqual(report['ids'], [462])
        self.assertIn('binding_model_id', report['columns'])
        self.assertEqual(role['key'], 'uid')
        self.assertEqual(role['columns'], ['uid', 'gid'])
        self.assertEqual(role['ids'], [462])

    def test_production_names_and_unreviewed_identifiers_are_rejected(self):
        for database in ('CERROELPLOMO', 'SYS', 'LAB_TAREAS', 'MANAGEMENT_QA_CERRO_PAYROLL_API_X;DROP'):
            with self.subTest(database=database), self.assertRaises(ValueError):
                guard.render_sql(database, self.specs())
        specs = self.specs()
        specs[0]['columns'].append('bad; sql')
        with self.assertRaisesRegex(ValueError, 'unsafe-guard-identifier'):
            guard.render_sql('MANAGEMENT_QA_CERRO_PAYROLL_API_TEST', specs)


if __name__ == '__main__':
    unittest.main()
