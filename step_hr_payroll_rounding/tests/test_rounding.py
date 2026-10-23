from datetime import date
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRounding(TransactionCase):
    def slip(self, start=date(2026, 10, 1), state='draft'):
        company = self.env['res.company'].new({'name': 'Rounding test',
            'currency_id': self.env.ref('base.CLP').id})
        structure = self.env['hr.payroll.structure'].new({'name': 'Rounding test',
            'type_id': self.env.ref('l10n_cl_simpledigital_payroll.structure_type_chile').id})
        return self.env['hr.payslip'].new({'company_id': company, 'struct_id': structure,
            'employee_id': self.env['hr.employee'].new({'name': 'Rounding test'}),
            'contract_id': self.env['hr.contract'].new({'name': 'Rounding test', 'wage': 553553}),
            'date_from': start, 'date_to': start.replace(day=28), 'state': state})

    def test_native_category_totals(self):
        for days, deduction, expected in [(28, 134034, (738071, 633904)),
                                          (29, 192790, (761136, 599279))]:
            with self.subTest(days=days):
                slip = self.slip()
                rules = self.env['hr.salary.rule']
                categories = {code: self.env['hr.salary.rule.category'].new({'name':code,'code':code})
                              for code in ('IMP','GROSS','NOP_IMP','DED','NET')}
                specs = [('BASIC','IMP',f'result = 553553 / 30 * {days}'),
                         ('BONUS','IMP','result = 73808'),
                         ('GRAT','IMP',"result = categories['IMP'] * .25"),
                         ('GROSS','GROSS',"result = categories['IMP']"),
                         ('COLA','NOP_IMP',f'result = 32000 / 30 * {days}'),
                         ('DED','DED',f'result = {deduction}'),
                         ('NET','NET',"result = categories['GROSS'] + categories['NOP_IMP'] - categories['DED']")]
                for index, (code, category, expression) in enumerate(specs):
                    rules |= self.env['hr.salary.rule'].new({'name':code, 'code':code,
                        'category_id':categories[category], 'sequence':index+1,
                        'condition_select':'none', 'amount_select':'code',
                        'amount_python_compute':expression})
                slip.struct_id.rule_ids = rules
                # This engine test supplies its own rule inputs; work-entry
                # generation belongs to the separate real-destination rehearsal.
                slip.worked_days_line_ids = self.env['hr.payslip.worked_days']
                slip.input_line_ids = self.env['hr.payslip.input']
                lines = {line['code']:line['total'] for line in slip._get_payslip_lines()}
                self.assertEqual(lines['GROSS'], expected[0])
                self.assertEqual(lines['NET'], expected[1])
                self.assertEqual(lines['GROSS'], lines['BASIC']+lines['BONUS']+lines['GRAT'])

    def test_round_final_quantity_rate_and_signed_halves(self):
        slip = self.slip()
        rule = self.env['hr.salary.rule']
        self.assertEqual(slip._get_payslip_line_total(100.25, 3, 50, rule), 150)
        self.assertEqual(slip._get_payslip_line_total(2.5, 1, 100, rule), 3)
        self.assertEqual(slip._get_payslip_line_total(-2.5, 1, 100, rule), -3)

    def test_effective_date_and_historical_states(self):
        for state in ('draft','verify','done','paid','cancel'):
            for month in (9,10):
                slip = self.slip(date(2026,month,1),state)
                total = slip._get_payslip_line_total(10.6,1,100,self.env['hr.salary.rule'])
                self.assertEqual(total,11 if month==10 and state in ('draft','verify') else 10.6)
        slip = self.slip()
        slip.company_id.currency_id = self.env.ref('base.USD')
        self.assertEqual(slip._get_payslip_line_total(10.6,1,100,self.env['hr.salary.rule']),10.6)
        slip.company_id.currency_id = self.env.ref('base.CLP')
        slip.struct_id.type_id = self.env['hr.payroll.structure.type'].new({'name':'Other'})
        self.assertEqual(slip._get_payslip_line_total(10.6,1,100,self.env['hr.salary.rule']),10.6)
