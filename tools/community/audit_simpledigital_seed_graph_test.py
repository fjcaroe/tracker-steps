"""Static graph tests: no Odoo, database, business formulas or XML evaluation."""
import json
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


if __name__ == '__main__':
    unittest.main()
