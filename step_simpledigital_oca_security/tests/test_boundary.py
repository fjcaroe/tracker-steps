"""Exercise actual supplier/OCA records and native ID aliases with real users."""
from odoo import api, Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from werkzeug.exceptions import BadRequest, Forbidden
from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin
from ..controllers import authorized_company


@tagged('post_install','-at_install')
class SimpleDigitalBoundary(PayrollContractMixin,TransactionCase):
    @classmethod
    def setUpClass(cls):
        cls.payroll_group='payroll.group_payroll_manager'
        super().setUpClass()
        cls.oca=bool(cls.env['ir.module.module'].search_count([('name','=','payroll'),('state','=','installed')]))

    def employee_user(self,login):
        user=self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private supplier employee','login':login,'company_id':self.company.id,
            'company_ids':[Command.set(self.company.ids)],
            'groups_id':[Command.set([self.env.ref(g).id for g in ('base.group_user','l10n_cl_simpledigital_payroll.group_hr_payroll_employee')])]})
        return user

    def test_native_aliases_reuse_original_ids(self):
        if not self.oca:
            for alias,original in [('group_payroll_user','group_hr_payroll_user'),('group_payroll_manager','group_hr_payroll_manager')]+[('model_'+m,'model_'+m) for m in ('hr_payslip','hr_payslip_line','hr_payslip_input','hr_payslip_worked_days')]:
                self.assertEqual(self.env.ref('payroll.'+alias),self.env.ref('hr_payroll.'+original))
        else:
            self.assertFalse(self.env['ir.module.module'].search_count([('name','=','hr_payroll'),('state','=','installed')]))
            self.assertEqual(self.env['hr.payslip']._table,'hr_payslip')
            self.assertEqual(self.env['hr.payslip']._fields['line_ids'].comodel_name,'hr.payslip.line')

    def test_employee_own_salary_and_foreign_salary_denied(self):
        owner=self.employee_user('private-sd-owner');other=self.employee_user('private-sd-other')
        self.employee.user_id=owner
        slip=self.slip();slip.compute_sheet()
        self.assertTrue(slip.with_user(owner).read(['line_ids']))
        self.assertTrue(slip.line_ids.with_user(owner).read(['total']))
        self.assertTrue(slip.input_line_ids.with_user(owner).read(['amount']))
        for record,columns in [(slip,['line_ids']),(slip.line_ids,['total']),(slip.input_line_ids,['amount'])]:
            with self.assertRaises(AccessError):record.with_user(other).read(columns)
        if self.oca:
            with self.assertRaises(AccessError):slip.line_ids.with_user(owner).read(['amount_python_compute'])

    def test_employee_cannot_download_company_exports(self):
        user=self.employee_user('private-sd-export')
        env=api.Environment(self.env.cr,user.id,dict(self.env.context,allowed_company_ids=self.company.ids),su=False)
        with self.assertRaises(Forbidden):authorized_company(env,self.company.id)

    def test_manager_export_guard_checks_active_company(self):
        self.assertEqual(authorized_company(self.scope,self.company.id),self.company.id)
        with self.assertRaises(Forbidden):authorized_company(self.scope,self.env.company.id)
        with self.assertRaises(BadRequest):authorized_company(self.scope,'invalid')

    def test_existing_provider_fields_and_views_load(self):
        for model,names in {'hr.contract':['health_institution','pension_option','analytic_account_id','hourly_wage'],
                'hr.employee':['hr_commune'],'hr.payslip':['paid_amount','net_wage'],
                'hr.work.entry.type':['unpaid_structure_ids']}.items():
            self.assertTrue(set(names)<=set(self.scope[model]._fields))
        model=self.scope['hr.payslip']
        view=self.env.ref('payroll.hr_payslip_view_form' if self.oca else 'hr_payroll.view_hr_payslip_form')
        self.assertTrue(model.get_view(view_id=view.id,view_type='form')['arch'])
        self.assertTrue(self.env.ref('l10n_cl_simpledigital_payroll.structure_chile').exists())

    def test_chile_incomplete_masters_block_before_lines(self):
        self.structure.name='Nómina Chile'
        slip=self.slip()
        with self.assertRaises(UserError):slip.compute_sheet()
        self.assertFalse(slip.line_ids)
        self.assertEqual(slip.state,'draft')

    def test_company_rule_cannot_be_bypassed_by_context(self):
        slip=self.slip();slip.compute_sheet()
        with self.assertRaises(AccessError):
            slip.with_user(self.scope.user).with_context(allowed_company_ids=self.env.company.ids).read(['line_ids'])

    def test_unpaid_type_uses_actual_structure_relation(self):
        if not self.oca:
            return
        slip=self.slip()
        kind=self.scope['hr.work.entry.type'].create({'name':'Private unpaid','code':'PRIVATE_UNPAID',
            'unpaid_structure_ids':[Command.set(self.structure.ids)]})
        line=self.scope['hr.payslip.worked_days'].create({'payslip_id':slip.id,'contract_id':self.contract.id,
            'name':kind.name,'code':kind.code,'work_entry_type_id':kind.id,'number_of_days':1,'number_of_hours':8})
        self.assertFalse(line.is_paid);self.assertEqual(line.amount,0)
        kind.unpaid_structure_ids=[Command.clear()]
        self.assertTrue(line.is_paid);self.assertAlmostEqual(line.amount,self.contract.wage/30)

    def test_validated_salary_is_immutable(self):
        slip=self.slip();slip.compute_sheet();slip.state='done'
        before=slip.line_ids.read(['amount','quantity','total'])
        with self.assertRaises(UserError):slip.compute_sheet()
        self.assertEqual(slip.line_ids.read(['amount','quantity','total']),before)

    def test_inverse_input_membership_cannot_change_used_type(self):
        if not self.oca:return
        self.slip()
        original=self.input_type.struct_ids
        other=self.structure.copy({'name':'Private unrelated input structure','rule_ids':[Command.clear()]})
        self.assertEqual(self.input_type.struct_ids,original)
        with self.assertRaises(ValidationError):other.input_line_type_ids=[Command.link(self.input_type.id)]
        self.assertEqual(self.input_type.struct_ids,original)
        with self.assertRaises(ValidationError):
            self.structure.copy({'input_line_type_ids':[Command.link(self.input_type.id)]})
        self.assertEqual(self.input_type.struct_ids,original)

    def test_real_employee_action_and_provider_report(self):
        slip=self.slip();slip.compute_sheet()
        action=self.employee.action_view_payslips()
        self.assertEqual(action['res_model'],'hr.payslip')
        self.assertIn(slip,self.scope['hr.payslip'].search(action['domain']))
        for view_id,view_type in action['views']:
            self.assertTrue(self.scope['hr.payslip'].get_view(view_id=view_id,view_type=view_type)['arch'])
        if self.oca:
            report=self.env.ref('payroll.action_report_payslip')
            self.assertEqual(report.report_name,'step_simpledigital_oca_base.report_payslip')
            html,_=self.scope['ir.actions.report']._render_qweb_html('payroll.action_report_payslip',slip.ids)
            self.assertIn(b'payslip_lines_table',html)
            self.assertIn(b'Private API employee',html)
            self.assertFalse(self.scope.su)
