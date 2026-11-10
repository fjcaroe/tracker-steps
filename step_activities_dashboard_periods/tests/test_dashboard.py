from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class DashboardPeriodCase(TransactionCase):
    def test_periods_use_latest_activity_and_company(self):
        company = self.env['res.company'].create({'name': 'QA panel T187'})
        crews = self.env['hr.salary.custom'].with_company(company)
        self.env['step.temporada'].with_company(company).create({
            'name': 'QA T187', 'company_id': company.id,
            'start_date': date(2024, 8, 1), 'end_date': date(2025, 5, 1),
        })
        for day in (date(2024, 7, 31), date(2024, 8, 20), date(2024, 9, 2),
                    date(2024, 9, 9), date(2024, 9, 10)):
            crews.create({'name': 'QA T187', 'date': day, 'company_id': company.id})
        for period, count in (('day', 1), ('week', 2), ('month', 3), ('season', 4)):
            result = crews.get_activities_period_dashboard(period)
            self.assertEqual(result['kpis']['crews'], count, period)
            self.assertEqual(result['kpis']['total_cost'], 0)
        self.assertEqual(crews.get_activities_period_dashboard()['period'], 'day')
        self.assertEqual(crews.get_activities_dashboard_data(0)['kpis']['crews'], 5)
