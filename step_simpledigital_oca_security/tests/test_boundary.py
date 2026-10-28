"""Exercise actual supplier/OCA records and native ID aliases with real users."""
from odoo import api, Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from werkzeug.exceptions import BadRequest, Forbidden
from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin
from ..controllers import authorized_company
from odoo.addons.step_payroll_contracts.history import assert_history_snapshots, assert_community_engine


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
            self.assertTrue(self.scope.user.has_group('hr_payroll.group_hr_payroll_manager'))
            self.assertIn(self.env.ref('payroll.group_payroll_manager'),self.scope.user.groups_id)
        else:
            self.assertFalse(self.env['ir.module.module'].search_count([('name','=','hr_payroll'),('state','=','installed')]))
            self.assertEqual(self.env['hr.payslip']._table,'hr_payslip')
            self.assertEqual(self.env['hr.payslip']._fields['line_ids'].comodel_name,'hr.payslip.line')

    def test_employee_own_salary_and_foreign_salary_denied(self):
        owner=self.employee_user('private-sd-owner');other=self.employee_user('private-sd-other')
        self.employee.user_id=owner
        slip=self.slip();slip.compute_sheet()
        self.assertTrue(slip.with_user(owner).read(['line_ids']))
        public=self.scope['hr.employee.public'].with_user(owner).browse(self.employee.id)
        action=public.action_view_payslips()
        self.assertIn(slip,self.scope['hr.payslip'].with_user(owner).search(action['domain']))
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
                'hr.employee':['hr_commune'],'hr.payslip':['net_wage'],
                'hr.work.entry.type':['unpaid_structure_ids']}.items():
            self.assertTrue(set(names)<=set(self.scope[model]._fields),(model,set(names)-set(self.scope[model]._fields)))
        self.assertEqual(self.slip().paid_amount,self.contract.wage)
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
        self.structure.use_worked_day_lines=True
        self.assertFalse(line.is_paid);self.assertEqual(line.amount,0)
        self.assertEqual(slip.paid_amount,0)
        kind.unpaid_structure_ids=[Command.clear()]
        self.assertTrue(line.is_paid);self.assertEqual(line.amount,self.company.currency_id.round(self.contract.wage/30))
        self.assertEqual(slip.paid_amount,line.amount)
        self.assertEqual(slip.with_context(no_paid_amount=True).paid_amount,0)

    def test_validated_salary_is_immutable(self):
        slip=self.slip();slip.compute_sheet();slip.state='done'
        self.env.flush_all();slip.line_ids.invalidate_recordset()
        before=slip.line_ids.read(['amount','quantity','total'])
        with self.assertRaises(UserError):slip.compute_sheet()
        self.assertEqual(slip.line_ids.read(['amount','quantity','total']),before)
        for record,values in ((slip.input_line_ids,{'amount':999}),(slip.line_ids,{'amount':999})):
            with self.assertRaises(UserError):record.write(values)
            with self.assertRaises(UserError):record.unlink()
        with self.assertRaises(UserError):slip.input_line_ids.copy()

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

    def test_provider_required_metadata_matches_preserved_contract(self):
        fields=self.scope['hr.contract']._fields
        self.assertTrue(fields['income_tax_type'].required)
        self.assertTrue(fields['work_schedule_id'].required)
        self.assertTrue(self.scope['hr.payslip.line']._fields['code'].required)
        code=self.scope['hr.payslip.line']._fields['code']
        self.assertEqual(tuple(code.related.split('.') if isinstance(code.related,str) else code.related),('salary_rule_id','code'))
        self.assertTrue(code.readonly)
        slip=self.slip();slip.compute_sheet()
        self.env.flush_all();slip.line_ids.invalidate_recordset()
        before=slip.line_ids.read(['id','code','salary_rule_id'])
        slip._get_line_values(['LIQ'])
        self.assertEqual(slip.line_ids.read(['id','code','salary_rule_id']),before)
        self.assertIn(self.rule.code,slip.line_ids.mapped('code'))

    def test_history_admission_reads_original_stored_values(self):
        slip=self.slip();slip.compute_sheet();slip.state='done';self.env.flush_all()
        self.env.cr.execute('SELECT to_jsonb(t) FROM hr_payslip t WHERE id=%s',(slip.id,));before=self.env.cr.fetchone()
        assert_history_snapshots(self.env.cr)
        self.env.cr.execute('SELECT to_jsonb(t) FROM hr_payslip t WHERE id=%s',(slip.id,))
        self.assertEqual(self.env.cr.fetchone(),before)

    def test_incomplete_closed_snapshot_is_rejected_without_backfill(self):
        slip=self.slip();slip.compute_sheet();slip.state='done';self.env.flush_all()
        with self.assertRaises(UserError),self.env.cr.savepoint():
            self.env.cr.execute('UPDATE hr_payslip SET net_wage=NULL WHERE id=%s',(slip.id,))
            assert_history_snapshots(self.env.cr)
        self.env.cr.execute('SELECT net_wage IS NOT NULL FROM hr_payslip WHERE id=%s',(slip.id,))
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_native_engine_cannot_be_overlaid_by_community_bridge(self):
        if self.oca:
            assert_community_engine(self.env.cr)
        else:
            with self.assertRaises(UserError):assert_community_engine(self.env.cr)

    def valid_configuration(self):
        (self.structure.rule_ids-self.rule).unlink()
        self.rule.write({'code':'BASIC','amount_python_compute':'result = payslip.paid_amount','sequence':1})
        gross_cat=self.scope['hr.salary.rule.category'].create({'name':'Private structural gross','code':'PRIVATE_GROSS'})
        self.gross_rule=self.rule.copy({'code':'GROSS','sequence':100,'category_id':gross_cat.id,
            'amount_python_compute':"result = categories['PRIVATE_NET']"})
        self.net_rule=self.rule.copy({'code':'NET','sequence':200,
            'amount_python_compute':"result = categories.get('PRIVATE_GROSS', 0)"})

    def test_actual_provider_configuration_and_original_rule_aliases(self):
        # Grant this new fixture actor access to the original configuration company.
        company=self.env.company
        self.scope.user.sudo().write({'company_ids':[Command.link(company.id)]})
        original=self.env.ref('l10n_cl_simpledigital_payroll.structure_chile')
        structure=original.with_user(self.scope.user).with_context(allowed_company_ids=company.ids)
        before=structure.rule_ids.read(['id','code','category_id','amount_python_compute','sequence'])
        report=structure._step_configuration_report()
        self.assertFalse(report['financial_certified'])
        if report['errors']:
            with self.assertRaises(UserError):structure._step_validate_configuration()
        else:self.assertTrue(structure._step_validate_configuration()['structural_checks_passed'])
        self.assertEqual(structure.rule_ids.read(['id','code','category_id','amount_python_compute','sequence']),before)
        if not self.oca:
            for code in ('BASIC','GROSS','NET'):
                self.assertEqual(self.env.ref('step_simpledigital_oca_security.chile_rule_'+code.lower()),
                    structure.rule_ids.filtered(lambda rule:rule.code==code))
            from ..hooks import uninstall_hook
            original_ids=structure.rule_ids.ids
            uninstall_hook(self.env)
            self.assertEqual(structure.rule_ids.ids,original_ids)
            self.assertEqual(structure.rule_ids.read(['id','code','category_id','amount_python_compute','sequence']),before)
            self.assertFalse(self.env['ir.model.data'].search_count([('module','=','step_simpledigital_oca_security'),('name','in',['chile_rule_basic','chile_rule_gross','chile_rule_net'])]))
        else:self.assertTrue({'BASIC_MISSING','GROSS_MISSING','NET_MISSING'}<=set(report['errors']))

    def test_structural_configuration_and_real_category_parent_bridge(self):
        self.valid_configuration()
        self.assertTrue(self.structure._step_validate_configuration()['structural_checks_passed'])
        proxy=self.scope['hr.salary.rule.category'].create({'name':'Private parent category','code':'PRIVATE_PROXY'})
        self.rule.category_id.parent_id=proxy
        self.gross_rule.amount_python_compute="result = categories.PRIVATE_PROXY"
        self.assertTrue(self.structure._step_validate_configuration()['structural_checks_passed'])

    def test_disconnected_gross_is_rejected_without_rewriting_configuration(self):
        self.valid_configuration()
        self.gross_rule.amount_python_compute="result = categories.get('PRIVATE_GROSS', 0)"
        before=self.gross_rule.read(['id','amount_python_compute','category_id'])
        with self.assertRaisesRegex(UserError,'GROSS_DISCONNECTED_FROM_BASIC'):
            self.structure._step_validate_configuration()
        self.assertEqual(self.gross_rule.read(['id','amount_python_compute','category_id']),before)

    def test_inactive_basic_cannot_silently_disappear_from_payroll(self):
        self.valid_configuration();self.rule.active=False
        with self.assertRaisesRegex(UserError,'BASIC_MISSING'):
            self.structure._step_validate_configuration()

    def test_essential_configuration_requires_execution_order(self):
        self.valid_configuration();self.gross_rule.sequence=201
        with self.assertRaisesRegex(UserError,'ESSENTIAL_SEQUENCE'):
            self.structure._step_validate_configuration()

    def test_configuration_is_checked_before_any_payroll_calculation(self):
        self.valid_configuration()
        self.structure.name='Nómina Chile'
        self.gross_rule.amount_python_compute="result = categories.get('PRIVATE_GROSS', 0)"
        slip=self.slip()
        with self.assertRaisesRegex(UserError,'GROSS_DISCONNECTED_FROM_BASIC'):slip.compute_sheet()
        self.assertFalse(slip.line_ids)
        self.assertEqual(slip.state,'draft')
