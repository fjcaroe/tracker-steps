from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDailyAccounting(TransactionCase):
    def test_missing_masters_are_reported_before_creating_an_entry(self):
        company = self.env['res.company'].create({'name': 'QA Costeo de labores'})
        tasks = self.env['step.tarja'].with_company(company)
        task = tasks.create({'name': 'QA Tarea', 'company_id': company.id, 'date': '2026-11-04'})
        task.state = 'costo'
        self.env['step.tarja.line'].with_company(company).create({'tarja_id': task.id, 'hrs': 8})

        with self.assertRaises(UserError) as error:
            task.action_conta()

        for detail in ('Diario Transitorio', 'Temporadas', 'Haberes de costeo',
                       'Centro de costos', 'cuenta analítica Actividad'):
            self.assertIn(detail, str(error.exception))
        self.assertEqual(task.state, 'costo')
        self.assertFalse(task.invoice_id)
