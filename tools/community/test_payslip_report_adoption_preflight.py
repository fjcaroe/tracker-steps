import unittest
from payslip_report_adoption_preflight import assess, COMMUNITY_RENDERER
from build_simpledigital_candidate import adapt_payslip_report_xml


class PayslipReportAdmissionCase(unittest.TestCase):
    def contract(self):
        return {'actions': [], 'reports': [], 'xmlids': [], 'template_keys': [COMMUNITY_RENDERER]}

    def test_unrelated_action_collision_never_authorizes_overwrite(self):
        data = self.contract()
        data['actions'] = [{'id': 462, 'type': 'ir.actions.act_window'}]
        result = assess(data)
        self.assertIn('ORIGINAL_ACTION_ID_COLLISION', result['blockers'])
        self.assertFalse(result['numeric_id_available'])
        self.assertFalse(result['conversion_ready'])

    def test_legacy_alias_to_other_report_does_not_preserve_original_id(self):
        data = self.contract()
        data['xmlids'] = [{'module': 'hr_payroll', 'name': 'action_report_payslip',
                          'model': 'ir.actions.report', 'res_id': 515}]
        self.assertIn('LEGACY_ALIAS_DOES_NOT_PRESERVE_NUMERIC_ID', assess(data)['blockers'])

    def test_existing_native_name_is_not_a_community_renderer_alias(self):
        data = self.contract()
        data['actions'] = [{'id': 462, 'type': 'ir.actions.report'}]
        data['reports'] = [{'id': 462, 'model': 'hr.payslip', 'report_type': 'qweb-pdf',
                            'report_name': 'hr_payroll.report_payslip_lang'}]
        result = assess(data)
        self.assertIn('ORIGINAL_ACTION_NOT_ADOPTED_TO_REAL_COMMUNITY_RENDERER', result['blockers'])
        self.assertFalse(result['functional_pdf_certified'])

    def test_free_numeric_space_is_only_reservable_not_a_conversion(self):
        result = assess(self.contract())
        self.assertTrue(result['numeric_id_available'])
        self.assertFalse(result['dependencies_may_change'])
        self.assertFalse(result['conversion_ready'])

    def test_real_community_template_is_required(self):
        data = self.contract();data['template_keys'] = []
        self.assertIn('COMMUNITY_TEMPLATE_MISSING', assess(data)['blockers'])

    def test_provider_transform_uses_stored_values_and_preserves_null_guard(self):
        source = '''<odoo><template><t t-set="plines" t-value="o.line_ids.filtered(lambda l: l.appears_on_payslip)"/>
            <t t-set="worked_days_lines" t-value="o.worked_days_line_ids.filtered(lambda worked_days: worked_days.code != 'OUT')"/>
            <t t-set="hab_lines" t-value="plines.filtered(lambda l: l.category_id.code in hab_cats)"/>
            <span t-out="hl.total"/><span t-out="dl.total"/><span t-out="o.net_wage"/>
            <div t-if="o.overtime_hours > 0"><span t-out="round(o.overtime_hours, 2)"/></div>
            <t t-set="style" t-value="'bold' if hl.category_id.code else ''"/>
            <div id="signature_section"/>
        </template></odoo>'''
        result = adapt_payslip_report_xml(source)
        self.assertNotIn('o.net_wage', result)
        self.assertNotIn('o.overtime_hours', result)
        self.assertNotIn('hstep_report_category', result)
        self.assertIn('step_report_category(hl)', result)
        self.assertIn('step_report_net(o) is not None', result)
        self.assertIn('page-break-inside: avoid', result)
        with self.assertRaisesRegex(AssertionError, 'signature structure drift'):
            adapt_payslip_report_xml(source.replace('<div id="signature_section"/>', ''))

    def test_provider_structure_drift_is_not_silently_accepted(self):
        with self.assertRaises(AssertionError):
            adapt_payslip_report_xml('<odoo><template/></odoo>')


if __name__ == '__main__':
    unittest.main()
