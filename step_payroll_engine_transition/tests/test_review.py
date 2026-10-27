from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class PayrollReviewCase(TransactionCase):
    def contract(self, name):
        employee = self.env['hr.employee'].new({'name': name, 'company_id': self.env.company.id})
        return self.env['hr.contract'].new({'name': 'Contrato ' + name, 'employee_id': employee,
            'company_id': self.env.company.id, 'step_payroll_migration_review': True})

    def slip(self, contract):
        return self.env['hr.payslip'].new({'employee_id': contract.employee_id,
            'contract_id': contract, 'company_id': self.env.company.id, 'struct_id': False})

    def test_batch_identifies_every_pending_contract_and_keeps_review_gate(self):
        first, second = self.contract('QA Persona A'), self.contract('QA Persona B')
        slips = self.slip(first) | self.slip(second)
        with self.assertRaises(UserError) as error:
            slips.compute_sheet()
        for name in ('QA Persona A', 'QA Persona B', 'Confirmar parámetros de nómina'):
            self.assertIn(name, str(error.exception))
        self.assertTrue(first.step_payroll_migration_review)
        self.assertTrue(second.step_payroll_migration_review)

    def test_same_contract_is_not_repeated_for_multiple_slips(self):
        contract = self.contract('QA Unico')
        with self.assertRaises(UserError) as error:
            (self.slip(contract) | self.slip(contract)).compute_sheet()
        self.assertEqual(str(error.exception).count('Contrato QA Unico'), 1)

    def test_missing_parameter_is_named_instead_of_generic_failure(self):
        contract = self.contract('QA Incompleto')
        if 'health_institution' in contract._fields:
            contract.health_institution = False
            label = contract._fields['health_institution'].get_description(self.env)['string']
            self.assertIn(label, contract._step_simpledigital_review_lines())
        else:
            self.assertIn('Simple Digital', contract._step_simpledigital_review_lines())

    def test_direct_flag_write_remains_protected(self):
        with self.assertRaises(UserError):
            self.contract('QA Protegido').write({'step_payroll_migration_review': False})

    def test_non_manager_cannot_confirm(self):
        contract = self.contract('QA Acceso')
        with self.assertRaises(UserError):
            contract.with_user(self.env.ref('base.public_user')).action_confirm_payroll_migration()
        self.assertTrue(contract.step_payroll_migration_review)

    def test_legacy_payslip_cannot_be_recalculated(self):
        contract = self.contract('QA Historico')
        slip = self.slip(contract)
        slip.struct_id = self.env['hr.payroll.structure'].new({'name': 'QA Historica', 'step_legacy_payroll': True})
        with self.assertRaises(UserError) as error:
            slip.compute_sheet()
        self.assertIn('No se recalcula', str(error.exception))
