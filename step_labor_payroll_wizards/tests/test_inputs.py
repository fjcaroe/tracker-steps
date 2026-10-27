"""Input routing against the real installed payroll/provider, with new fixtures only."""
from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class PayrollInputCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company=cls.env['res.company'].create({'name':'Private input fixture'})
        cls.env=cls.env(context=dict(cls.env.context,allowed_company_ids=cls.company.ids))
        cls.structure=cls.env['hr.payroll.structure'].create({'name':'Private input structure',
            'type_id':cls.env['hr.payroll.structure.type'].create({'name':'Private input type'}).id})
        cls.input_type=cls.env['hr.payslip.input.type'].create({'name':'Private bonus','code':'PRIVATE_BONUS',
            'struct_ids':[Command.set(cls.structure.ids)]})
        cls.batch=cls.env['hr.payslip.run'].create({'name':'Private input run','company_id':cls.company.id})
        cls.employee=cls.env['hr.employee'].create({'name':'Private input employee','company_id':cls.company.id})
        cls.user=cls.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private input user','login':'private-input-user','company_id':cls.company.id,
            'company_ids':[Command.set(cls.company.ids)],'groups_id':[Command.set(cls.env.ref('base.group_user').ids)]})
        cls.employee.user_id=cls.user
        values={'name':'Private input contract','employee_id':cls.employee.id,'company_id':cls.company.id,
            'date_start':fields.Date.today().replace(day=1),'wage':800000,'structure_type_id':cls.structure.type_id.id}
        field=cls.env['hr.contract']._fields.get('contract_type_id')
        if field:
            values['contract_type_id']=cls.env[field.comodel_name].search([],limit=1).id
        cls.contract=cls.env['hr.contract'].create(values)
        cls.slip=cls.make_slip()

    @classmethod
    def make_slip(cls, **values):
        vals={'name':'Private input slip','employee_id':cls.employee.id,'contract_id':cls.contract.id,
              'company_id':cls.company.id,'struct_id':cls.structure.id,'payslip_run_id':cls.batch.id,
              'date_from':fields.Date.today().replace(day=1),'date_to':fields.Date.today()}
        vals.update(values)
        return cls.env['hr.payslip'].create(vals)

    def wizard(self, **values):
        vals={'payslip_run_id':self.batch.id,'struct_id':self.structure.id,'input_type_id':self.input_type.id,
              'user_ids':[Command.set(self.user.ids)],'value_amount':12345.67}
        vals.update(values)
        return self.env['hr.input.step.wizard'].create(vals)

    def test_exact_batch_and_contract_not_first_employee_slip(self):
        other=self.env['hr.payslip.run'].create({'name':'Other private run','company_id':self.company.id})
        earlier=self.make_slip(payslip_run_id=other.id)
        lines_before=self.slip.line_ids.read(['total','amount'])
        result=self.wizard().import_button()
        self.assertEqual(result['res_model'],'success.message')
        self.assertEqual(len(self.slip.input_line_ids),1)
        self.assertEqual(self.slip.input_line_ids.contract_id,self.contract)
        self.assertEqual(self.slip.input_line_ids.amount,12345.67)
        self.assertFalse(earlier.input_line_ids)
        self.assertEqual(self.slip.line_ids.read(['total','amount']),lines_before)
        self.assertEqual(self.slip.state,'draft')

    def test_paid_flag_and_all_non_draft_states_block_without_recalculation(self):
        original=self.slip.line_ids.read(['total','amount'])
        for state in ('verify','done','paid','cancel'):
            if state not in dict(self.slip._fields['state']._description_selection(self.env)):
                continue
            self.slip.state=state
            with self.subTest(state=state),self.assertRaises(ValidationError):
                self.wizard().import_button()
            self.assertFalse(self.slip.input_line_ids)
            self.assertEqual(self.slip.line_ids.read(['total','amount']),original)
        self.slip.write({'state':'draft','paid':True})
        with self.assertRaises(ValidationError):self.wizard().import_button()
        self.assertFalse(self.slip.input_line_ids)

    def test_ambiguous_slips_reject_before_creating_inputs(self):
        duplicate=self.make_slip()
        with self.assertRaises(ValidationError):self.wizard().import_button()
        self.assertFalse((duplicate|self.slip).input_line_ids)

    def test_missing_employee_slip_rejects_entire_selection(self):
        second=self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private missing employee','login':'private-input-missing','company_id':self.company.id,
            'company_ids':[Command.set(self.company.ids)]})
        with self.assertRaises(ValidationError):
            self.wizard(user_ids=[Command.set((self.user|second).ids)]).import_button()
        self.assertFalse(self.slip.input_line_ids)

    def test_repeat_import_does_not_duplicate_input(self):
        wizard=self.wizard();wizard.import_button()
        original=self.slip.input_line_ids.read(['amount','contract_id'])
        with self.assertRaises(ValidationError):wizard.import_button()
        self.assertEqual(self.slip.input_line_ids.read(['amount','contract_id']),original)

    def test_wrong_structure_and_input_type_rejected(self):
        structure=self.structure.copy({'name':'Other private structure'})
        with self.assertRaises(ValidationError):self.wizard(struct_id=structure.id).import_button()
        self.assertFalse(self.slip.input_line_ids)

    def test_cross_company_run_rejected(self):
        other=self.env['res.company'].create({'name':'Other private input company'})
        run=self.env['hr.payslip.run'].create({'name':'Other company run','company_id':other.id})
        with self.assertRaises(ValidationError):self.wizard(payslip_run_id=run.id).import_button()
        self.assertFalse(self.slip.input_line_ids)

    def test_closed_run_rejected(self):
        state=next(s for s,_ in self.batch._fields['state']._description_selection(self.env) if s!='draft')
        self.batch.state=state
        with self.assertRaises(ValidationError):self.wizard().import_button()
        self.assertFalse(self.slip.input_line_ids)

    def test_empty_selection_rejected(self):
        with self.assertRaises(ValidationError):self.wizard(user_ids=[Command.clear()]).import_button()

    def test_original_acl_not_bypassed(self):
        wizard=self.wizard()
        with self.assertRaises(AccessError):wizard.with_user(self.user).import_button()
        self.assertFalse(self.slip.input_line_ids)
