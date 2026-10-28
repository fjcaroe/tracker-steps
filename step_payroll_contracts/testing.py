"""Shared assertions executed against real OCA and real Enterprise reference engines."""
from datetime import datetime, time, timedelta

import pytz

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError


class PayrollContractMixin:
    payroll_group = None
    oca = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company=cls.env['res.company'].create({'name':'Private payroll API fixture','country_id':cls.env.ref('base.cl').id,'currency_id':cls.env.ref('base.CLP').id})
        actor=cls.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private payroll API manager','login':'private-payroll-api-manager','tz':'UTC',
            'company_id':company.id,'company_ids':[Command.set(company.ids)],
            'groups_id':[Command.set([cls.env.ref(g).id for g in
                ('base.group_user',cls.payroll_group,'account.group_account_manager','hr.group_hr_manager')])]})
        cls.scope=api.Environment(cls.env.cr,actor.id,dict(cls.env.context,allowed_company_ids=company.ids),su=False)
        cls.company=company
        scope=cls.scope
        cls.journal=scope['account.journal'].create({'name':'Private payroll API journal','code':'PAP','type':'general','company_id':company.id})
        cls.debit=scope['account.account'].create({'name':'Private payroll API cost','code':'940001','account_type':'expense','company_ids':[Command.set(company.ids)]})
        cls.credit=scope['account.account'].create({'name':'Private payroll API debt','code':'940002','account_type':'liability_current','company_ids':[Command.set(company.ids)]})
        cls.kind=scope['hr.payroll.structure.type'].create({'name':'Private API type'})
        values={'name':'Private API structure','code':'PRIVATE_API','type_id':cls.kind.id}
        if 'company_id' in scope['hr.payroll.structure']._fields:values['company_id']=company.id
        if 'parent_id' in scope['hr.payroll.structure']._fields:values['parent_id']=False
        if 'use_worked_day_lines' in scope['hr.payroll.structure']._fields:values['use_worked_day_lines']=False
        if 'journal_id' in scope['hr.payroll.structure']._fields:values['journal_id']=cls.journal.id
        cls.structure=scope['hr.payroll.structure'].create(values)
        cls.rule=scope['hr.salary.rule'].create({'name':'Private real API rule','code':'LIQ','sequence':1,
            'struct_id':cls.structure.id,'category_id':scope['hr.salary.rule.category'].create({'name':'Private API net','code':'PRIVATE_NET'}).id,
            'condition_select':'none','amount_select':'code','quantity':'1.0',
            'amount_python_compute':"result = contract.wage + inputs['PRIVATE_BONUS'].amount",
            'account_debit':cls.debit.id,'account_credit':cls.credit.id})
        cls.input_type=scope['hr.payslip.input.type'].create({'name':'Private API bonus','code':'PRIVATE_BONUS','struct_ids':[Command.set(cls.structure.ids)]})
        cls.employee=scope['hr.employee'].create({'name':'Private API employee','company_id':company.id})
        vals={'name':'Private API contract','employee_id':cls.employee.id,'company_id':company.id,
            'state':'open','date_start':fields.Date.today().replace(day=1),'wage':800000,'structure_type_id':cls.kind.id}
        if 'struct_id' in scope['hr.contract']._fields:vals['struct_id']=cls.structure.id
        if 'journal_id' in scope['hr.contract']._fields:vals['journal_id']=cls.journal.id
        field=scope['hr.contract']._fields.get('contract_type_id')
        if field:vals['contract_type_id']=scope[field.comodel_name].search([],limit=1).id
        if scope['hr.contract']._fields.get('analytic_account_id') and scope['hr.contract']._fields['analytic_account_id'].required:
            plan=scope['account.analytic.plan'].create({'name':'Private payroll analytic plan'})
            vals['analytic_account_id']=scope['account.analytic.account'].create({'name':'Private payroll cost center','plan_id':plan.id,'company_id':company.id}).id
        cls.contract=scope['hr.contract'].create(vals)
        cls.env['ir.sequence'].create({'name':'Private salary API numbering','code':'salary.slip','company_id':company.id,'prefix':'API/'})

    def slip(self, amount=123.45):
        slip=self.scope['hr.payslip'].create({'name':'Private API payslip','employee_id':self.employee.id,
            'company_id':self.company.id,'contract_id':self.contract.id,'struct_id':self.structure.id,
            'date_from':fields.Date.today().replace(day=1),'date_to':fields.Date.today()})
        self.scope['hr.payslip.input'].create({'name':'Private typed bonus','payslip_id':slip.id,
            'contract_id':self.contract.id,'input_type_id':self.input_type.id,'amount':amount})
        return slip

    def test_real_engine_typed_input_and_liquid_code(self):
        slip=self.slip();slip.compute_sheet()
        self.assertFalse(slip.env.su)
        self.assertEqual(slip.input_line_ids.code,'PRIVATE_BONUS')
        self.assertAlmostEqual(slip._get_line_values(['LIQ'])['LIQ'][slip.id]['total'],self.company.currency_id.round(800123.45))
        self.assertEqual(slip.input_line_ids.contract_id,self.contract)

    def test_line_values_missing_codes_and_multi_slip_sum(self):
        first=self.slip(10);second=self.slip(20);slips=first|second;slips.compute_sheet()
        result=slips._get_line_values(['LIQ','MISSING'],['amount','quantity','total'],compute_sum=True)
        for slip,expected in [(first,800010),(second,800020)]:
            self.assertAlmostEqual(result['LIQ'][slip.id]['total'],expected)
            self.assertEqual(result['MISSING'][slip.id]['total'],0)
        self.assertAlmostEqual(result['LIQ']['sum']['total'],1600030)
        self.assertEqual(result['MISSING']['sum']['total'],0)

    def test_line_values_reads_do_not_change_validated_lines(self):
        slip=self.slip();slip.compute_sheet();slip.state='done'
        before=slip.line_ids.read(['amount','quantity','total'])
        slip._get_line_values(['LIQ','MISSING'],compute_sum=True)
        self.assertEqual(slip.line_ids.read(['amount','quantity','total']),before)
        self.assertEqual(slip.state,'done')

    def test_rules_receive_real_record_and_mapping_get(self):
        self.rule.amount_python_compute='result = 321.25 if payslip.env.company.id == contract.company_id.id and worked_days.get("PRIVATE_ABSENT") is None and inputs.get("PRIVATE_ABSENT") is None else -999'
        slip=self.slip();slip.compute_sheet()
        self.assertAlmostEqual(slip._get_line_values(['LIQ'])['LIQ'][slip.id]['total'],self.company.currency_id.round(321.25))

    def test_actual_accounting_entry_balances(self):
        slip=self.slip();slip.compute_sheet();slip.action_payslip_done()
        self.assertTrue(slip.move_id)
        self.assertAlmostEqual(sum(slip.move_id.line_ids.mapped('balance')),0)
        self.assertAlmostEqual(sum(slip.move_id.line_ids.mapped('debit')),self.company.currency_id.round(800123.45))

    def test_portal_cannot_read_salary_lines(self):
        slip=self.slip();slip.compute_sheet()
        portal=self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private API portal','login':'private-api-portal','groups_id':[Command.set(self.env.ref('base.group_portal').ids)]})
        with self.assertRaises(AccessError):slip.with_user(portal).read(['line_ids'])

    def test_repeated_input_amounts_aggregate_without_changing_rows(self):
        slip=self.slip(10)
        slip.input_line_ids.copy({'amount':20})
        original=slip.input_line_ids.read(['id','amount','contract_id','input_type_id'])
        slip.compute_sheet()
        self.assertEqual(slip._get_line_values(['LIQ'])['LIQ'][slip.id]['total'],800030)
        self.assertEqual(slip.input_line_ids.read(['id','amount','contract_id','input_type_id']),original)

    def test_repeated_input_nonlinear_rule_is_evaluated_per_line(self):
        self.rule.write({'code':'PRIVATE_BONUS',
            'amount_python_compute':"result = inputs['PRIVATE_BONUS'].amount ** 2"})
        self.rule.copy({'code':'PRIVATE_RESULT_CHAIN','sequence':2,
            'amount_python_compute':"result = result_rules['PRIVATE_BONUS']['total']"})
        slip=self.slip(2);slip.input_line_ids.copy({'amount':3});slip.compute_sheet()
        lines=slip.line_ids.filtered(lambda line:line.code=='PRIVATE_BONUS')
        self.assertEqual(len(lines),2)
        if self.oca:
            self.assertEqual(slip.get_salary_line_total('PRIVATE_BONUS'),13)
        self.assertEqual(slip._get_line_values(['PRIVATE_BONUS'])['PRIVATE_BONUS'][slip.id]['total'],13)
        self.assertEqual(len(slip.input_line_ids),2)
        self.assertEqual(slip._get_line_values(['PRIVATE_RESULT_CHAIN'])['PRIVATE_RESULT_CHAIN'][slip.id]['total'],13)

    def test_quantities_rates_and_categories_preserve_clp_rounding(self):
        self.input_type.is_quantity=True
        self.rule.write({'code':'PRIVATE_BONUS',
            'amount_python_compute':"result = 100.6\nresult_qty = inputs['PRIVATE_BONUS'].amount\nresult_rate = 50"})
        self.rule.copy({'code':'PRIVATE_CHAIN','sequence':2,'amount_python_compute':"result = categories['PRIVATE_NET']"})
        slip=self.slip(0.5);slip.input_line_ids.copy({'amount':1.5});slip.compute_sheet()
        values=slip._get_line_values(['PRIVATE_BONUS','PRIVATE_CHAIN'])
        self.assertEqual(values['PRIVATE_BONUS'][slip.id]['total'],100)
        self.assertEqual(values['PRIVATE_CHAIN'][slip.id]['total'],101)
        self.env.flush_all()
        slip.line_ids.invalidate_recordset()
        self.assertEqual(slip._get_line_values(['PRIVATE_BONUS'])['PRIVATE_BONUS'][slip.id]['total'],100)

    def test_fractional_negative_rate_uses_real_engine(self):
        self.rule.amount_python_compute='result = -10.6\nresult_qty = 1.5\nresult_rate = 50'
        slip=self.slip();slip.compute_sheet()
        self.env.flush_all();slip.line_ids.invalidate_recordset()
        values=slip._get_line_values(['LIQ'],['amount','quantity','total'])['LIQ'][slip.id]
        self.assertEqual(values,{'amount':-11.0,'quantity':1.5,'total':-8.0})

    def work_calendar(self, tz='UTC'):
        calendar=self.scope['resource.calendar'].create({'name':'Private actual payroll calendar',
            'company_id':self.company.id,'tz':tz,'attendance_ids':[Command.clear()]+[
                Command.create({'name':'Private shift','dayofweek':str(day),'hour_from':8,'hour_to':16,'day_period':'morning'})
                for day in range(5)]})
        self.contract.resource_calendar_id=calendar
        self.employee.resource_calendar_id=calendar
        self.employee.resource_id.tz=tz
        return calendar

    def test_actual_work_entries_types_and_domain(self):
        self.work_calendar()
        slip=self.slip()
        first=fields.Date.today().replace(day=1)
        monday=first+timedelta(days=(-first.weekday())%7)
        work=self.scope['hr.work.entry.type'].create({'name':'Private actual attendance','code':'PAPI_WORK','sequence':10})
        leave=self.scope['hr.work.entry.type'].create({'name':'Private actual leave','code':'PAPI_LEAVE','is_leave':True,'sequence':20})
        entries=self.scope['hr.work.entry'].create([
            {'name':'Private work','employee_id':self.employee.id,'contract_id':self.contract.id,'company_id':self.company.id,
             'work_entry_type_id':work.id,'date_start':datetime.combine(monday,time(8)),'date_stop':datetime.combine(monday,time(12))},
            {'name':'Private leave','employee_id':self.employee.id,'contract_id':self.contract.id,'company_id':self.company.id,
             'work_entry_type_id':leave.id,'date_start':datetime.combine(monday,time(12)),'date_stop':datetime.combine(monday,time(16))}])
        self.assertEqual(work.round_days_type,'DOWN')
        leave.round_days='HALF';leave.round_days_type='HALF-UP'
        self.assertEqual(slip._round_days(leave,0.25),0.5)
        before=entries.read(['date_start','date_stop','duration','state','contract_id','work_entry_type_id'])
        rows={row['work_entry_type_id']:row for row in slip._get_worked_day_lines_values()}
        self.assertAlmostEqual(rows[work.id]['number_of_hours'],4)
        self.assertAlmostEqual(rows[work.id]['number_of_days'],0.5)
        self.assertAlmostEqual(rows[leave.id]['number_of_hours'],4)
        filtered=slip._get_worked_day_lines_values([('work_entry_type_id','=',leave.id)])
        self.assertEqual([row['work_entry_type_id'] for row in filtered],[leave.id])
        self.assertEqual(entries.read(['date_start','date_stop','duration','state','contract_id','work_entry_type_id']),before)

    def test_calendar_timezone_clips_work_entry_at_payroll_boundary(self):
        self.work_calendar('America/Santiago')
        slip=self.slip()
        zone=pytz.timezone('America/Santiago')
        boundary=zone.localize(datetime.combine(slip.date_from,time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        kind=self.scope['hr.work.entry.type'].create({'name':'Private boundary attendance','code':'PAPI_BOUNDARY'})
        self.scope['hr.work.entry'].create({'name':'Private crossing entry','employee_id':self.employee.id,
            'contract_id':self.contract.id,'company_id':self.company.id,'work_entry_type_id':kind.id,
            'date_start':boundary-timedelta(hours=2),'date_stop':boundary+timedelta(hours=3)})
        hours=self.contract.get_work_hours(slip.date_from,slip.date_to)
        self.assertAlmostEqual(hours[kind.id],3,places=5)

    def chile_rounding_structure(self):
        if self.oca:
            self.structure.step_clp_concept_rounding=True
        else:
            self.structure.type_id=self.env.ref('l10n_cl_simpledigital_payroll.structure_type_chile')

    def test_chile_concept_rounding_matches_known_salary_cases(self):
        self.chile_rounding_structure()
        for days,deduction,expected in [(28,134034,(738071,633904)),(29,192790,(761136,599279))]:
            self.structure=self.structure.copy({'name':'Private Chile case '+str(days),'rule_ids':[Command.clear()]})
            self.input_type=self.input_type.copy({'code':'PRIVATE_CASE_'+str(days),'struct_ids':[Command.set(self.structure.ids)]})
            categories={code:self.scope['hr.salary.rule.category'].create({'name':'Private '+code,'code':code})
                        for code in ('IMP','GROSS','NOP_IMP','DED','NET')}
            specs=[('BASIC','IMP',f'result = 553553 / 30 * {days}'),
                   ('BONUS','IMP','result = 73808'),
                   ('GRAT','IMP',"result = categories['IMP'] * .25"),
                   ('GROSS','GROSS',"result = categories['IMP']"),
                   ('COLA','NOP_IMP',f'result = 32000 / 30 * {days}'),
                   ('DED','DED',f'result = {deduction}'),
                   ('NET','NET',"result = categories['GROSS'] + categories['NOP_IMP'] - categories['DED']")]
            rules=self.scope['hr.salary.rule']
            for index,(code,category,formula) in enumerate(specs):
                rules |= self.scope['hr.salary.rule'].create({'name':'Private '+code,'code':code,
                    'category_id':categories[category].id,'sequence':index+1,'struct_id':self.structure.id,
                    'condition_select':'none','amount_select':'code','amount_python_compute':formula})
            slip=self.slip();slip.compute_sheet()
            values=slip._get_line_values(['BASIC','BONUS','GRAT','GROSS','NET'])
            actual=lambda code:values[code][slip.id]['total']
            self.assertEqual((actual('GROSS'),actual('NET')),expected)
            self.assertEqual(actual('GROSS'),sum(actual(code) for code in ('BASIC','BONUS','GRAT')))

    def test_chile_final_quantity_rate_and_signed_halves(self):
        self.chile_rounding_structure()
        slip=self.slip()
        for amount,qty,rate,expected in [(100.25,3,50,150),(2.5,1,100,3),(-2.5,1,100,-3)]:
            self.assertEqual(slip._get_payslip_line_total(amount,qty,rate,self.rule),expected)

    def test_out_of_contract_days_use_original_calendar(self):
        self.work_calendar()
        slip=self.slip()
        self.contract.date_start=slip.date_from+timedelta(days=3)
        if self.oca:
            kind=self.scope['hr.work.entry.type'].create({'name':'Private out of contract','code':'PAPI_OUT'})
            self.structure.out_of_contract_work_entry_type_id=kind
        else:
            kind=self.env.ref('hr_payroll.hr_work_entry_type_out_of_contract')
        rows=[row for row in slip._get_worked_day_lines() if row['work_entry_type_id']==kind.id]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['number_of_hours'],16)
        self.assertEqual(rows[0]['number_of_days'],2)
        self.assertFalse(slip._get_worked_day_lines(check_out_of_contract=False))

    def _stored_identity_fixture(self, code, distinct):
        # Use actual engine/model rows. Reproduce a historical duplicate before
        # closing; the reader must not choose a rule or reconstruct the amounts.
        self.rule.write({'code':code,'amount_python_compute':"result = inputs['PRIVATE_BONUS'].amount"})
        slip=self.slip(125);slip.compute_sheet()
        line=slip.line_ids.filtered(lambda row:row.code==code)
        self.assertEqual(len(line),1)
        rule=self.rule.copy({'name':'Private historical second rule'}) if distinct else self.rule
        line.copy({'salary_rule_id':rule.id,'amount':0,'quantity':1,'rate':100})
        slip.state='done';self.env.flush_all()
        return slip

    def _identity_snapshot(self, slip):
        self.env.flush_all()
        self.env.cr.execute('SELECT id,code,salary_rule_id,total,write_date FROM hr_payslip_line WHERE slip_id=%s ORDER BY id',(slip.id,))
        return self.env.cr.fetchall()

    def test_stored_essential_distinct_rule_identities_are_not_summed(self):
        from odoo.addons.step_payroll_contracts.history import stored_payslip_code_totals,stored_payslip_totals
        slip=self._stored_identity_fixture('NET',True);before=self._identity_snapshot(slip)
        with self.assertRaisesRegex(UserError,'multiple rule identities'):stored_payslip_code_totals(slip)
        with self.assertRaisesRegex(UserError,'multiple rule identities'):stored_payslip_totals(slip,'NET')
        self.assertEqual(stored_payslip_totals(slip,'PRIVATE_ABSENT'),{slip.id:0})
        self.assertEqual(self._identity_snapshot(slip),before)

    def test_stored_same_rule_rows_remain_additive_and_stable(self):
        from odoo.addons.step_payroll_contracts.history import stored_payslip_code_totals
        slip=self._stored_identity_fixture('NET',False);before=self._identity_snapshot(slip)
        self.assertEqual(stored_payslip_code_totals(slip),{slip.id:{'NET':125}})
        self.contract.wage=1200000
        self.assertEqual(stored_payslip_code_totals(slip),{slip.id:{'NET':125}})
        self.assertEqual(self._identity_snapshot(slip),before)

    def test_stored_nonessential_distinct_rules_keep_additive_contract(self):
        from odoo.addons.step_payroll_contracts.history import stored_payslip_code_totals
        slip=self._stored_identity_fixture('PRIVATE_HISTORY',True);before=self._identity_snapshot(slip)
        self.assertEqual(stored_payslip_code_totals(slip),{slip.id:{'PRIVATE_HISTORY':125}})
        self.assertEqual(self._identity_snapshot(slip),before)
