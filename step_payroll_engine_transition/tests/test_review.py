from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class PayrollReviewCase(TransactionCase):
    def contract(self, name, review=True):
        employee = self.env['hr.employee'].create({'name': name, 'company_id': self.env.company.id})
        return self.env['hr.contract'].create({'name': 'Contrato ' + name, 'employee_id': employee.id,
            'date_start':'2026-01-01','wage':1000,'resource_calendar_id':self.env.company.resource_calendar_id.id,
            'company_id': self.env.company.id, 'step_payroll_migration_review': review})

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

    def test_regular_chilean_batch_names_all_incomplete_contracts(self):
        structure = self.env.ref('l10n_cl_simpledigital_payroll.structure_chile', raise_if_not_found=False)
        if not structure:
            self.skipTest('Requires Simple Digital')
        first = self.contract('QA Sin Salud', review=False)
        second = self.contract('QA Sin Comuna', review=False)
        first.health_institution = False
        second.employee_id.hr_commune = False
        slips = self.env['hr.payslip'].create([
            {
                'name': 'QA Simple Digital',
                'employee_id': contract.employee_id.id,
                'contract_id': contract.id,
                'company_id': contract.company_id.id,
                'struct_id': structure.id,
                'date_from': '2026-10-01',
                'date_to': '2026-10-31',
            }
            for contract in (first, second, first)
        ])

        with self.assertRaises(UserError) as error:
            slips.compute_sheet()
        message = str(error.exception)
        self.assertEqual(message.count(first.name), 1, message)
        self.assertIn(first._fields['health_institution'].get_description(self.env)['string'], message)
        self.assertIn(second.name, message)
        self.assertIn('Comuna del trabajador', message)
        self.assertNotIn('Confirmar parámetros de nómina', message)

    def test_non_manager_cannot_confirm(self):
        contract = self.contract('QA Acceso')
        with self.assertRaises(UserError):
            contract.with_user(self.env.ref('base.public_user')).action_confirm_payroll_migration()
        self.assertTrue(contract.step_payroll_migration_review)

    def test_legacy_payslip_cannot_be_recalculated(self):
        structure = self.env['hr.payroll.structure'].new({'name': 'QA Historica', 'step_legacy_payroll': True})
        slip = self.env['hr.payslip'].new({'struct_id':structure})
        with self.assertRaises(UserError) as error:
            slip.compute_sheet()
        self.assertIn('No se recalcula', str(error.exception))
