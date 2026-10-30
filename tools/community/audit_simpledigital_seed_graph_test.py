"""Static graph tests: no Odoo, database, business formulas or XML evaluation."""
import json
import ast
from pathlib import Path
import tempfile
import unittest

import audit_simpledigital_seed_graph as graph


class SeedGraphCase(unittest.TestCase):
    def addon(self, folder, files):
        addon = Path(folder) / 'provider'
        addon.mkdir()
        (addon / '__manifest__.py').write_text(repr({'license': 'AGPL-3', 'data': list(files)}))
        for name, content in files.items():
            path = addon / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return addon

    def test_omitted_seed_reference_has_exact_owner_field_and_file(self):
        with tempfile.TemporaryDirectory() as folder:
            addon = self.addon(folder, {
                'data/rules.xml': '<odoo><record id="basic" model="hr.salary.rule"><field name="amount_python_compute">PRIVATE FORMULA MUST NEVER EXPORT</field></record></odoo>',
                'views/settings.xml': '<odoo><record id="settings" model="ir.ui.view"><field name="inherit_id" ref="base.layout"/><field name="binding" ref="basic"/></record></odoo>'})
            report = graph.analyze_addon(addon, omit=['data/rules.xml'])
            self.assertEqual(len(report['removed_seed_blockers']), 1)
            edge = report['removed_seed_blockers'][0]
            self.assertEqual((edge['file'], edge['owner'], edge['field'], edge['target']),
                ('views/settings.xml', 'provider.settings', 'binding', 'provider.basic'))
            self.assertNotIn('PRIVATE FORMULA', json.dumps(report))
            self.assertEqual(report['remaining_salary_master_records'], [])
            self.assertFalse(report['bootstrap_certified'])

    def test_remaining_salary_record_is_reported_and_external_targets_are_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            addon = self.addon(folder, {'data/types.xml': '<odoo><record id="external.original" model="hr.payroll.structure.type"/></odoo>'})
            report = graph.analyze_addon(addon)
            self.assertEqual(len(report['remaining_salary_master_records']), 1)
            self.assertTrue(report['remaining_salary_master_records'][0]['external_target'])

    def test_qweb_refs_are_runtime_and_never_evaluated_or_owned_by_html_id(self):
        xml = b'''<odoo><template id="report"><div id="signature"><t t-call="web.external_layout"/><t t-if="env.ref('provider.basic')"/><t t-if="env.ref(candidate)"/></div></template></odoo>'''
        report = graph.scan_xml(xml, 'report/layout.xml', 'provider')
        self.assertEqual({r['target'] for r in report['refs']}, {'provider.basic', 'web.external_layout'})
        self.assertTrue(all(r['owner'] == 'provider.report' for r in report['refs']))
        self.assertTrue(all(r['kind'].startswith('runtime') for r in report['refs']))
        self.assertEqual(len(report['dynamic_refs']), 1)
        refs, dynamic = graph.expression_refs("__import__('builtins').print('DO NOT RUN') or ref('base.cl')", 'provider')
        self.assertEqual(refs, ['base.cl'])
        self.assertFalse(dynamic)

    def test_csv_model_ids_and_action_placeholders_are_explicit_requirements(self):
        csv = b'id,name,model_id:id,group_id:id\naccess_x,SECRET LABEL,model_x,base.group_user\n'
        report = graph.scan_csv(csv, 'security/ir.model.access.csv', 'provider')
        self.assertEqual({r['target'] for r in report['refs']}, {'provider.model_x', 'base.group_user'})
        self.assertNotIn('SECRET LABEL', json.dumps(report))
        xml = b'<odoo><record id="view" model="ir.ui.view"><field name="arch"><button name="%(provider.open_action)d" type="action"/></field></record></odoo>'
        self.assertEqual(graph.scan_xml(xml, 'views.xml', 'provider')['refs'][0]['target'], 'provider.open_action')

    def test_source_pin_allowlist_path_and_enterprise_boundaries_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            addon = self.addon(folder, {'data/types.xml': '<odoo/>'})
            with self.assertRaises(AssertionError): graph.analyze_addon(addon, allowed_files=set())
            (addon / '__manifest__.py').write_text(repr({'license': 'OEEL-1', 'data': ['data/types.xml']}))
            with self.assertRaises(AssertionError): graph.analyze_addon(addon)
        for name in ('../private.xml', '/absolute.xml', 'data//x.xml', 'data\\x.xml'):
            with self.assertRaises(AssertionError): graph.relative(name)

    def test_dtd_xxe_utf16_and_invalid_xml_bodies_never_escape(self):
        for content in (b'<!DOCTYPE x [<!ENTITY p SYSTEM "file:///etc/passwd">]><x>&p;</x>', b'<x>\x00</x>'):
            with self.assertRaises(AssertionError): graph.scan_xml(content, 'fixture.xml', 'provider')
        try:
            graph.scan_xml(b'<x PRIVATE_FORMULA', 'fixture.xml', 'provider')
        except ValueError as error:
            self.assertNotIn('PRIVATE_FORMULA', str(error))
        else:
            self.fail('Malformed XML was accepted')

    def test_explicit_omitted_files_can_describe_an_already_filtered_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            addon = self.addon(folder, {'data/rules.xml': '<odoo><record id="basic" model="hr.salary.rule"/></odoo>',
                'views/settings.xml': '<odoo><record id="view" model="ir.ui.view"><field name="x" ref="basic"/></record></odoo>'})
            (addon / '__manifest__.py').write_text(repr({'license': 'AGPL-3', 'data': ['views/settings.xml']}))
            report = graph.analyze_addon(addon, omit=['data/rules.xml'])
            self.assertEqual(report['removed_xmlids'], ['provider.basic'])
            self.assertEqual(len(report['removed_seed_blockers']), 1)

    def profiles(self, folder):
        normal = Path(folder) / 'normal' / graph.MODULE
        profile = Path(folder) / 'cold' / graph.MODULE
        fragment = '<field name="unpaid_structure_ids" eval="[(4, ref(\'l10n_cl_simpledigital_payroll.structure_chile\'))]"/>'
        files = {'__init__.py': '# unchanged runtime\n',
            'data/hr_salary_rule.xml': '<odoo><record id="basic" model="hr.salary.rule"><field name="amount_python_compute">PRIVATE FORMULA MUST NEVER EXPORT</field></record></odoo>',
            'data/hr_salary_structure.xml': '<odoo><record id="structure_chile" model="hr.payroll.structure"/></odoo>',
            graph.MOVEMENT_SEED_FILE: '<odoo><record id="movement_type" model="hr.employee.movement.type"/><record id="movement_event" model="hr.employee.hr.event.type"><field name="movement_id" ref="movement_type"/></record></odoo>',
            graph.DEFER_FILE: '<odoo><record id="work_entry_type_unpaid_cl" model="hr.work.entry.type"><field name="name">Ausencia sin goce</field>' + fragment + '</record></odoo>',
            'views/form.xml': '<odoo><record id="form" model="ir.ui.view"><field name="inherit_id" ref="base.layout"/></record></odoo>'}
        data = [name for name in files if name.endswith('.xml')]
        spec = {'license': 'AGPL-3', 'depends': ['step_simpledigital_oca_base'], 'data': data}
        files['__manifest__.py'] = repr(spec)
        filtered = {name: content for name, content in files.items() if name not in graph.BOOTSTRAP_SEED_FILES}
        filtered['__manifest__.py'] = repr(dict(spec, data=[name for name in data if name not in graph.BOOTSTRAP_SEED_FILES]))
        filtered[graph.DEFER_FILE] = files[graph.DEFER_FILE].replace(fragment, '')
        for root, snapshot in ((normal, files), (profile, filtered)):
            for name, content in snapshot.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content.encode())
        return normal, profile, set(files)

    def test_profile_proves_only_one_actual_deferred_link_without_claiming_adoption(self):
        with tempfile.TemporaryDirectory() as folder:
            normal, profile, allowed = self.profiles(folder)
            report = graph.verify_bootstrap_profile(normal, profile, allowed_files=allowed)
            self.assertEqual(report['omitted_salary_seed_files'], list(graph.SALARY_SEED_FILES))
            self.assertEqual(report['omitted_salary_xmlids'], [graph.MODULE + '.basic', graph.DEFER_TARGET])
            self.assertEqual(report['omitted_seed_files'], list(graph.BOOTSTRAP_SEED_FILES))
            self.assertEqual(report['deferred_movement_catalog']['model_counts'],
                {'hr.employee.movement.type': 1, 'hr.employee.hr.event.type': 1})
            self.assertFalse(report['deferred_movement_catalog']['adopted'])
            self.assertFalse(report['deferred_movement_catalog']['original_catalog_preserved_in_target'])
            self.assertFalse(report['deferred_movement_catalog']['generated_salary_rules_adopted'])
            self.assertFalse(report['deferred_movement_catalog']['rule_generation_executed'])
            self.assertEqual(report['remaining_salary_master_records'], [])
            self.assertEqual(report['other_local_orphans'], [])
            self.assertTrue(report['deferred_original_unpaid_link']['assignment_absent_in_profile'])
            self.assertFalse(report['deferred_original_unpaid_link']['original_policy_preserved_in_target'])
            self.assertFalse(report['identity_adopted'])
            self.assertFalse(report['bootstrap_certified'])
            self.assertNotIn('PRIVATE FORMULA', json.dumps(report))

    def test_profile_never_waives_a_present_dangling_assignment_or_an_extra_orphan(self):
        for mutation in ('present-assignment', 'another-removed-ref', 'removed-movement-ref', 'missing-local-ref'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                normal, profile, allowed = self.profiles(folder)
                if mutation == 'present-assignment':
                    (profile / graph.DEFER_FILE).write_bytes((normal / graph.DEFER_FILE).read_bytes())
                else:
                    target = {'another-removed-ref': 'basic', 'removed-movement-ref': 'movement_type'}.get(mutation, 'missing')
                    for root in (normal, profile):
                        path = root / 'views/form.xml'
                        path.write_bytes(path.read_bytes().replace(b'</record>',
                            ('<field name="other" ref="%s"/></record>' % target).encode()))
                with self.assertRaises(AssertionError):
                    graph.verify_bootstrap_profile(normal, profile, allowed_files=allowed)

    def test_profile_rejects_unapproved_runtime_manifest_type_or_field_changes(self):
        for mutation in ('runtime', 'manifest', 'type-value', 'extra-file', 'retained-seed', 'retained-movement', 'fourth-omission'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                normal, profile, allowed = self.profiles(folder)
                if mutation == 'runtime':
                    (profile / '__init__.py').write_text('# other runtime\n')
                elif mutation == 'manifest':
                    path = profile / '__manifest__.py'
                    spec = ast.literal_eval(path.read_text())
                    spec['depends'] = ['hr_payroll']
                    path.write_text(repr(spec))
                elif mutation == 'type-value':
                    path = profile / graph.DEFER_FILE
                    path.write_bytes(path.read_bytes().replace(b'Ausencia', b'Alterada'))
                elif mutation == 'extra-file':
                    (profile / 'new.py').write_text('')
                elif mutation == 'fourth-omission':
                    (profile / 'views/form.xml').unlink()
                    path = profile / '__manifest__.py'
                    spec = ast.literal_eval(path.read_text())
                    spec['data'].remove('views/form.xml')
                    path.write_text(repr(spec))
                else:
                    name = graph.MOVEMENT_SEED_FILE if mutation == 'retained-movement' else graph.SALARY_SEED_FILES[0]
                    (profile / name).write_bytes((normal / name).read_bytes())
                with self.assertRaises(AssertionError):
                    graph.verify_bootstrap_profile(normal, profile, allowed_files=allowed)

    def test_profile_rejects_different_link_semantics_or_ambiguous_field_owner(self):
        for mutation in ('replace-command', 'different-model', 'duplicate-span'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                normal, profile, allowed = self.profiles(folder)
                path = normal / graph.DEFER_FILE
                content = path.read_bytes()
                if mutation == 'replace-command':
                    content = content.replace(b'[(4, ref(', b'[(6, 0, ref(')
                elif mutation == 'different-model':
                    content = content.replace(b'model="hr.work.entry.type"', b'model="hr.employee"')
                else:
                    content = content.replace(b'</record>', b'<field name="unpaid_structure_ids" eval="[]"/></record>')
                path.write_bytes(content)
                with self.assertRaises(AssertionError):
                    graph.verify_bootstrap_profile(normal, profile, allowed_files=allowed)


if __name__ == '__main__':
    unittest.main()
