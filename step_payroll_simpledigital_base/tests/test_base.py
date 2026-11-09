from odoo.tests import TransactionCase, tagged

from ..models import COMPANY_PARAMETER, LEGACY_GROSS


@tagged('post_install', '-at_install')
class TestSimpleDigitalBase(TransactionCase):
    def test_only_selected_company_uses_taxable_category_for_legacy_rule(self):
        structure = self.env.ref('l10n_cl_simpledigital_payroll.structure_chile')
        company = self.env.company
        other = self.env['res.company'].create({'name': 'QA Base Imponible'})
        rule = self.env['hr.salary.rule'].new({
            'struct_id': structure.id, 'code': 'GROSS',
            'amount_select': 'code', 'amount_python_compute': LEGACY_GROSS,
        })
        categories = {'BASIC': 0.0, 'ALW': 0.0, 'IMP': 690_000.0, 'NOP_IMP': 100_000.0}
        slips = self.env['hr.payslip']
        self.env['ir.config_parameter'].set_param(COMPANY_PARAMETER, str(company.id))
        for owner, expected in ((company, 690_000.0), (other, 0.0)):
            localdict = {'payslip': slips.new({'company_id': owner.id}), 'categories': categories}
            self.assertEqual(rule._compute_rule(localdict), (expected, 1.0, 100.0))

        rule.amount_python_compute = 'result = 123'
        localdict = {'payslip': slips.new({'company_id': company.id}), 'categories': categories}
        self.assertEqual(rule._compute_rule(localdict), (123.0, 1.0, 100.0))
