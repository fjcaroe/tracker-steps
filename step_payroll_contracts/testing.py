"""Shared assertions executed against real OCA and real Enterprise reference engines."""
from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError


class PayrollContractMixin:
    payroll_group = None
    oca = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company=cls.env['res.company'].create({'name':'Private payroll API fixture','country_id':cls.env.ref('base.us').id})
        actor=cls.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private payroll API manager','login':'private-payroll-api-manager','tz':'UTC',
            'company_id':company.id,'company_ids':[Command.set(company.ids)],
            'groups_id':[Command.set([cls.env.ref(g).id for g in
                ('base.group_user',cls.payroll_group,'account.group_account_manager')])]})
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
            'amount_python_compute':'result = contract.wage + inputs.PRIVATE_BONUS.amount',
            'account_debit':cls.debit.id,'account_credit':cls.credit.id})
        cls.input_type=scope['hr.payslip.input.type'].create({'name':'Private API bonus','code':'PRIVATE_BONUS','struct_ids':[Command.set(cls.structure.ids)]})
        cls.employee=scope['hr.employee'].create({'name':'Private API employee','company_id':company.id})
        vals={'name':'Private API contract','employee_id':cls.employee.id,'company_id':company.id,
            'state':'open','date_start':fields.Date.today().replace(day=1),'wage':800000,'structure_type_id':cls.kind.id}
        if 'struct_id' in scope['hr.contract']._fields:vals['struct_id']=cls.structure.id
        if 'journal_id' in scope['hr.contract']._fields:vals['journal_id']=cls.journal.id
        field=scope['hr.contract']._fields.get('contract_type_id')
        if field:vals['contract_type_id']=scope[field.comodel_name].search([],limit=1).id
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
        self.assertAlmostEqual(slip._get_line_values(['LIQ'])['LIQ'][slip.id]['total'],800123.45)
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
        self.rule.amount_python_compute='result = 321.25 if payslip.env.company.id == contract.company_id.id and worked_days.get("PRIVATE_ABSENT") is None else -999'
        slip=self.slip();slip.compute_sheet()
        self.assertAlmostEqual(slip._get_line_values(['LIQ'])['LIQ'][slip.id]['total'],321.25)

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
