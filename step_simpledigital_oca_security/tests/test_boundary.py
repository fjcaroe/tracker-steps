"""Exercise actual supplier/OCA records and native ID aliases with real users."""
from types import SimpleNamespace
from unittest.mock import patch

from odoo import api, Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, HttpCase, tagged
from werkzeug.exceptions import BadRequest, Forbidden
from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin
from ..controllers import authorized_company, Book
from .. import controllers as secured_book
from odoo.addons.step_payroll_contracts.history import stored_payslip_totals
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

    def test_monthly_basis_structure_reports_explicit_worked_day_codes(self):
        self.valid_configuration()
        self.rule.amount_python_compute=self.monthly_basis_fixture_formula()
        before=self.rule.read(['id','amount_python_compute','category_id','sequence'])
        report=self.structure._step_validate_configuration()
        self.assertEqual(report['basic_basis']['worked_day_codes'],['PRIVATE_DAY_A','PRIVATE_DAY_B'])
        self.assertEqual(report['basic_basis']['divisor'],30)
        self.assertFalse(report['financial_certified'])
        self.assertEqual(self.rule.read(['id','amount_python_compute','category_id','sequence']),before)

    def test_monthly_basis_cannot_hide_quantity_rate_or_arbitrary_code(self):
        self.valid_configuration();formula=self.monthly_basis_fixture_formula()
        for invalid in [formula.replace('/ 30.0','/ 31.0'),formula.replace('a + b','a - b'),
                'result_qty = 2\n'+formula,'result_rate = 50\n'+formula,
                formula.replace('monthly = contract.wage or 0.0','monthly = payslip._get_contract_wage()')]:
            self.rule.amount_python_compute=invalid
            with self.assertRaisesRegex(UserError,'BASIC_UNVERIFIED_AMOUNT'):self.structure._step_validate_configuration()

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

    def duplicate_rules(self):
        (self.structure.rule_ids-self.rule).unlink()
        self.rule.write({'code':'NET','sequence':200,'amount_python_compute':'result = 10'})
        second=self.rule.copy({'name':'Private second NET','amount_python_compute':'result = 30'})
        category=self.scope['hr.salary.rule.category'].create({'name':'Private observer','code':'PRIVATE_OBSERVER'})
        observer=self.rule.copy({'code':'PRIVATE_OBSERVER','sequence':201,'category_id':category.id,
            'amount_python_compute':"result = categories['PRIVATE_NET']"})
        return second,observer

    def test_same_sequence_duplicate_net_uses_original_id_order(self):
        second,observer=self.duplicate_rules()
        before=(self.rule|second).read(['id','active','sequence','code','amount_python_compute','category_id'])
        slip=self.slip();slip.compute_sheet()
        lines=slip.line_ids.filtered(lambda line:line.code=='NET')
        self.assertEqual(len(lines),1)
        self.assertEqual(lines.salary_rule_id,second)
        self.assertEqual(lines.total,30)
        self.assertEqual(slip.line_ids.filtered(lambda line:line.salary_rule_id==observer).total,30)
        self.assertEqual((self.rule|second).read(['id','active','sequence','code','amount_python_compute','category_id']),before)
        if self.oca:
            self.assertEqual(slip._get_salary_rules().filtered(lambda rule:rule.code=='NET').ids,[self.rule.id,second.id])

    def test_conditional_duplicate_net_preserves_previous_result(self):
        second,observer=self.duplicate_rules()
        second.write({'condition_select':'python','condition_python':'result = False'})
        slip=self.slip();slip.compute_sheet()
        line=slip.line_ids.filtered(lambda line:line.code=='NET')
        self.assertEqual(line.salary_rule_id,self.rule)
        self.assertEqual(line.total,10)
        self.assertEqual(slip.line_ids.filtered(lambda line:line.salary_rule_id==observer).total,10)
        self.assertTrue(second.active)

    def test_ambiguous_net_reports_all_original_ids_without_adopting_one(self):
        self.valid_configuration()
        second=self.net_rule.copy({'name':'Private alternate NET'})
        before=(self.net_rule|second).read(['id','active','amount_python_compute'])
        report=self.structure._step_configuration_report()
        self.assertEqual(report['essential_candidate_ids']['NET'],[self.net_rule.id,second.id])
        self.assertIn('NET_AMBIGUOUS',report['errors'])
        self.assertNotIn('NET',report['essential_ids'])
        self.assertFalse(report['financial_certified'])
        with self.assertRaisesRegex(UserError,'NET_AMBIGUOUS'):self.structure._step_validate_configuration()
        self.assertEqual((self.net_rule|second).read(['id','active','amount_python_compute']),before)

    def test_nonessential_collision_stops_chile_before_existing_lines_change(self):
        self.valid_configuration()
        extra=self.rule.copy({'code':'PRIVATE_COLLISION','sequence':50,'amount_python_compute':'result = 10'})
        slip=self.slip();slip.compute_sheet();original_state=slip.state
        second=extra.copy({'category_id':self.gross_rule.category_id.id,
                           'condition_select':'python','condition_python':'result = False'})
        self.structure.name='Nómina Chile'
        self.env.flush_all()
        self.env.cr.execute('SELECT id,code,salary_rule_id,total,write_date FROM hr_payslip_line WHERE slip_id=%s ORDER BY id',(slip.id,))
        before=self.env.cr.fetchall()
        masters=(extra|second).read(['id','active','sequence','category_id','condition_python'])
        report=self.structure._step_configuration_report()
        self.assertEqual(report['duplicate_code_ids']['PRIVATE_COLLISION'],[extra.id,second.id])
        self.assertFalse(report['financial_certified'])
        with self.assertRaisesRegex(UserError,'RULE_CODE_AMBIGUOUS:PRIVATE_COLLISION'):slip.compute_sheet()
        self.env.flush_all()
        self.env.cr.execute('SELECT id,code,salary_rule_id,total,write_date FROM hr_payslip_line WHERE slip_id=%s ORDER BY id',(slip.id,))
        self.assertEqual(self.env.cr.fetchall(),before)
        self.assertEqual((extra|second).read(['id','active','sequence','category_id','condition_python']),masters)
        self.assertEqual(slip.state,original_state)

    def test_archived_and_other_structure_codes_are_not_collisions(self):
        self.valid_configuration()
        archived=self.net_rule.copy({'active':False})
        other=self.structure.copy({'name':'Private other configuration','rule_ids':[Command.clear()]})
        elsewhere=self.net_rule.copy({'struct_id':other.id})
        report=self.structure._step_validate_configuration()
        self.assertTrue(report['structural_checks_passed'])
        self.assertFalse(report['duplicate_code_ids'])
        self.assertFalse(archived.active)
        self.assertTrue(elsewhere.active)

    def ytd_configuration(self):
        (self.structure.rule_ids-self.rule).unlink()
        self.structure.ytd_computation=True
        self.company.write({'ytd_reset_day':1,'ytd_reset_month':'1'})
        self.rule.amount_python_compute="result = inputs['PRIVATE_BONUS'].amount"

    def period_slip(self,start,end,amount,closed=False):
        from datetime import date
        slip=self.slip(amount)
        slip.write({'date_from':date.fromisoformat(start),'date_to':date.fromisoformat(end)})
        slip.compute_sheet()
        if closed:slip.state='done'
        return slip

    def test_ytd_actual_calendar_window_states_and_overlapping_periods(self):
        self.ytd_configuration()
        self.period_slip('2025-12-01','2025-12-31',5,True)
        january=self.period_slip('2026-01-01','2026-01-31',10,True)
        self.period_slip('2026-02-01','2026-02-28',20)
        february=self.period_slip('2026-02-01','2026-02-28',30,True)
        self.period_slip('2026-04-01','2026-04-30',50,True)
        self.period_slip('2026-02-15','2026-03-15',15,True)
        current=self.period_slip('2026-03-01','2026-03-31',40)
        self.assertEqual(january.line_ids.ytd,10)
        self.assertEqual(february.line_ids.ytd,40)
        self.assertEqual(current.line_ids.ytd,95)
        self.assertEqual(current._get_line_values(['LIQ'],['total','ytd'])['LIQ'][current.id],{'total':40,'ytd':95})
        same=self.period_slip('2026-03-01','2026-03-31',9,True)
        current.compute_sheet()
        self.assertEqual(current.line_ids.ytd,104)
        self.assertEqual(same.line_ids.ytd,64)

    def test_ytd_disabled_retains_current_stored_total(self):
        self.ytd_configuration()
        self.period_slip('2026-01-01','2026-01-31',10,True)
        self.structure.ytd_computation=False
        current=self.period_slip('2026-02-01','2026-02-28',30)
        self.assertEqual(current.line_ids.ytd,30)
        self.assertEqual(current._get_line_values(['LIQ','MISSING'],['ytd'],compute_sum=True)['LIQ']['sum']['ytd'],30)

    def test_closed_ytd_read_is_stored_and_immutable(self):
        self.ytd_configuration()
        slip=self.period_slip('2026-01-01','2026-01-31',10,True)
        self.env.flush_all()
        self.env.cr.execute('SELECT to_jsonb(l) FROM hr_payslip_line l WHERE id=%s',(slip.line_ids.id,));before=self.env.cr.fetchone()
        self.contract.wage=1200000
        self.structure.ytd_computation=False
        self.env.flush_all();slip.line_ids.invalidate_recordset()
        self.assertEqual(slip._get_line_values(['LIQ'],['ytd'])['LIQ'][slip.id]['ytd'],10)
        self.env.cr.execute('SELECT to_jsonb(l) FROM hr_payslip_line l WHERE id=%s',(slip.line_ids.id,));self.assertEqual(self.env.cr.fetchone(),before)
        with self.assertRaises(UserError):slip.line_ids.ytd=999
        with self.assertRaises(UserError):slip.credit_note=True
        with self.assertRaises(UserError):slip.compute_sheet()

    def test_ytd_missing_original_snapshot_rejects_without_backfill(self):
        from odoo.addons.step_payroll_contracts.ytd import assert_ytd_snapshots
        self.ytd_configuration()
        slip=self.period_slip('2026-01-01','2026-01-31',10,True)
        self.env.flush_all();assert_ytd_snapshots(self.env.cr)
        with self.assertRaises(UserError),self.env.cr.savepoint():
            self.env.cr.execute('UPDATE hr_payslip_line SET ytd=NULL WHERE id=%s',(slip.line_ids.id,))
            assert_ytd_snapshots(self.env.cr)
        self.env.cr.execute('SELECT ytd FROM hr_payslip_line WHERE id=%s',(slip.line_ids.id,));self.assertEqual(self.env.cr.fetchone()[0],10)

    def test_community_ytd_rejects_unvalidated_resets_and_credit_notes(self):
        if not self.oca:return
        self.ytd_configuration();self.company.ytd_reset_month='2'
        slip=self.slip()
        with self.assertRaisesRegex(UserError,'Custom YTD resets'):slip.compute_sheet()
        self.assertFalse(slip.line_ids)
        self.company.ytd_reset_month='1';slip.credit_note=True
        with self.assertRaisesRegex(UserError,'Credit notes'):slip.compute_sheet()
        self.assertFalse(slip.line_ids)

    def test_community_ytd_repeated_lines_fail_atomically(self):
        if not self.oca:return
        self.ytd_configuration()
        self.rule.code=self.input_type.code
        slip=self.slip(10);slip.input_line_ids.copy({'amount':20})
        with self.assertRaisesRegex(UserError,'repeated concept lines'):slip.compute_sheet()
        self.assertFalse(slip.line_ids)
        self.assertEqual(len(slip.input_line_ids),2)

    def test_community_ytd_cannot_silently_skip_hidden_historical_lines(self):
        if not self.oca:return
        self.ytd_configuration()
        old=self.period_slip('2026-01-01','2026-01-31',10,True)
        self.env['ir.rule'].create({'name':'Private restricted historical concept',
            'model_id':self.env['ir.model']._get_id('hr.payslip.line'),
            'domain_force':repr([('id','!=',old.line_ids.id)]),
            'perm_read':True,'perm_write':False,'perm_create':False,'perm_unlink':False})
        current=self.slip(30)
        current.write({'date_from':'2026-02-01','date_to':'2026-02-28'})
        with self.assertRaises(AccessError):current.compute_sheet()
        self.assertFalse(current.line_ids)

    def test_closed_wage_basis_does_not_follow_current_contract(self):
        slip=self.slip();slip.compute_sheet();slip.state='done';self.env.flush_all()
        self.env.cr.execute('SELECT to_jsonb(s) FROM hr_payslip s WHERE id=%s',(slip.id,))
        before=self.env.cr.fetchone()
        self.contract.wage=1200000
        for method in ('_get_contract_wage','_get_paid_amount','_get_unpaid_amount'):
            with self.assertRaisesRegex(UserError,'stored wage basis'):
                getattr(slip,method)()
        with self.assertRaisesRegex(UserError,'stored wage basis'):
            _=slip.paid_amount
        self.env.flush_all()
        self.env.cr.execute('SELECT to_jsonb(s) FROM hr_payslip s WHERE id=%s',(slip.id,))
        self.assertEqual(self.env.cr.fetchone(),before)

    def test_closed_wage_basis_context_cannot_replace_history_with_zero(self):
        slip=self.slip();slip.compute_sheet();slip.state='done';self.env.flush_all()
        for context in ({'no_paid_amount':True},{'salary_simulation':True}):
            with self.assertRaisesRegex(UserError,'stored wage basis'):
                _=slip.with_context(**context).paid_amount
        self.assertTrue(slip.read(['basic_wage','gross_wage','net_wage']))

    def test_cancelled_wage_basis_is_not_a_draft_calculation(self):
        slip=self.slip();slip.compute_sheet();slip.state='cancel'
        for method in ('_get_contract_wage','_get_paid_amount','_get_unpaid_amount'):
            with self.assertRaisesRegex(UserError,'stored wage basis'):
                getattr(slip,method)()

    def test_wage_basis_checks_salary_visibility_before_history_state(self):
        slip=self.slip();slip.compute_sheet();slip.state='done'
        stranger=self.employee_user('private-sd-wage-stranger')
        for method in ('_get_contract_wage','_get_paid_amount','_get_unpaid_amount'):
            with self.assertRaises(AccessError):
                getattr(slip.with_user(stranger),method)()

    def closed_book_slip(self, total=0, inactive=False):
        slip=self.slip();slip.compute_sheet();self.env.flush_all()
        self.env.cr.execute('UPDATE hr_payslip_line SET amount=100,total=%s WHERE slip_id=%s',(total,slip.id))
        if inactive and 'active' in slip.line_ids._fields:
            slip.line_ids.active=False
        slip.line_ids.invalidate_recordset();slip.state='done';self.env.flush_all()
        return slip

    def test_book_stored_zero_overrides_legacy_components(self):
        slip=self.closed_book_slip()
        self.env.cr.execute('SELECT to_jsonb(l) FROM hr_payslip_line l WHERE slip_id=%s',(slip.id,))
        before=self.env.cr.fetchall()
        self.contract.wage=1200000
        with patch.object(secured_book,'request',SimpleNamespace(env=self.scope)):
            self.assertEqual(Book()._get_payslip_lines(slip,'LIQ'),0)
        self.env.flush_all()
        self.env.cr.execute('SELECT to_jsonb(l) FROM hr_payslip_line l WHERE slip_id=%s',(slip.id,))
        self.assertEqual(self.env.cr.fetchall(),before)

    def test_book_missing_original_total_does_not_become_zero(self):
        slip=self.closed_book_slip()
        calls=(lambda:Book()._get_payslip_lines(slip,'LIQ'),
               lambda:Book()._get_payslips(slip.date_from,slip.date_to,self.company.id))
        for call in calls:
            with self.assertRaises(UserError),self.env.cr.savepoint():
                self.env.cr.execute('UPDATE hr_payslip_line SET total=NULL WHERE slip_id=%s',(slip.id,))
                with patch.object(secured_book,'request',SimpleNamespace(env=self.scope)):
                    call()
        self.assertEqual(stored_payslip_totals(slip),{slip.id:0})

    def test_book_hidden_salary_line_rejects_partial_total(self):
        slip=self.closed_book_slip(250)
        self.env['ir.rule'].create({'name':'Private hidden book salary line',
            'model_id':self.env['ir.model']._get_id('hr.payslip.line'),
            'domain_force':repr([('id','not in',slip.line_ids.ids)]),
            'perm_read':True,'perm_write':False,'perm_create':False,'perm_unlink':False})
        with patch.object(secured_book,'request',SimpleNamespace(env=self.scope)):
            with self.assertRaises(AccessError):Book()._get_payslip_lines(slip.sudo(),'LIQ')
            with self.assertRaises(AccessError):Book()._get_payslip_lines(slip.sudo(),'MISSING')
            with self.assertRaises(AccessError):Book()._get_payslips(slip.date_from,slip.date_to,self.company.id)

    def test_book_rebinds_elevated_payslip_to_http_actor(self):
        slip=self.closed_book_slip(250)
        other=self.employee_user('private-sd-book-stranger')
        scope=api.Environment(self.env.cr,other.id,dict(self.scope.context),su=False)
        with patch.object(secured_book,'request',SimpleNamespace(env=scope)):
            with self.assertRaises(AccessError):Book()._get_payslip_lines(slip.sudo())

    def test_book_queries_terminal_slips_without_elevation(self):
        closed=self.closed_book_slip(250)
        draft=self.slip()
        paid=self.closed_book_slip(300);paid.state='paid'
        with patch.object(secured_book,'request',SimpleNamespace(env=self.scope)):
            found=Book()._get_payslips(closed.date_from,closed.date_to,self.company.id)
            self.assertEqual(set(found.ids),{closed.id,paid.id})
            self.assertNotIn(draft,found);self.assertFalse(found.env.su)
            with self.assertRaises(Forbidden):Book()._get_payslips(closed.date_from,closed.date_to,self.env.company.id)
            with self.assertRaises(BadRequest):Book()._get_payslips(closed.date_to,closed.date_from.replace(day=1).replace(year=2025),self.company.id)

    def test_book_preserves_supplier_code_filter_and_integer_contract(self):
        first=self.closed_book_slip(12.9,inactive=True);second=self.closed_book_slip(-12.9)
        self.assertEqual(stored_payslip_totals(first|second,'LIQ'),{first.id:12.9,second.id:-12.9})
        with patch.object(secured_book,'request',SimpleNamespace(env=self.scope)):
            book=Book()
            self.assertEqual(book._get_payslip_lines(first,['LIQ','MISSING']),12)
            self.assertEqual(book._get_payslip_lines(second,'LIQ'),-12)
            self.assertEqual(book._get_payslip_lines(first,'MISSING'),0)
            # Native fixtures also contain the real engine's additional core lines.
            self.assertEqual(book._get_payslip_lines(first,[]),int(12.9*len(first.with_context(active_test=False).line_ids)))

    def test_book_invalid_parent_is_not_an_empty_report(self):
        with patch.object(secured_book,'request',SimpleNamespace(env=self.scope)):
            with self.assertRaises(UserError):Book()._get_payslip_lines(self.scope['hr.payslip'])
            with self.assertRaises(UserError):Book()._get_payslip_lines(self.scope['hr.payslip'].new({}))
        self.assertEqual(stored_payslip_totals(self.scope['hr.payslip']),{})


@tagged('post_install','-at_install')
class OwnBookConsumers(PayrollContractMixin,TransactionCase):
    """Actual own-library on OCA; registered own extractor on native reference."""
    payroll_group='payroll.group_payroll_manager'

    def movement_slip(self,total):
        kind=self.env['hr.employee.movement.type'].create({'name':'Private book movement','bono_ok':True,'earn_type':'imponible'})
        self.assertTrue(kind.salary_rule_id)
        self.rule.code=kind.salary_rule_id.code
        slip=self.slip();slip.compute_sheet();self.env.flush_all()
        self.env.cr.execute('UPDATE hr_payslip_line SET amount=100,total=%s WHERE slip_id=%s AND code=%s',
                            (total,slip.id,self.rule.code))
        slip.line_ids.invalidate_recordset();slip.state='done';self.env.flush_all()
        return slip,self.rule.code

    def adapter(self):
        import runpy
        from pathlib import Path
        from odoo.modules.module import get_module_path
        path=Path(get_module_path('step_hr_remuneration_book'))/'models/remuneration_book_adapter.py'
        # This file only defines the actual Python adapter registry. It does not
        # register ORM models or pretend the full native-dependent app is installed.
        return runpy.run_path(str(path))['MovementTypeRulesAdapter']

    def test_code_snapshots_preserve_original_zero_in_batch(self):
        from odoo.addons.step_payroll_contracts.history import stored_payslip_code_totals
        slip,code=self.movement_slip(0)
        other=self.slip();other.compute_sheet();self.env.flush_all()
        self.env.cr.execute('UPDATE hr_payslip_line SET total=-25 WHERE slip_id=%s AND code=%s',(other.id,code))
        other.line_ids.invalidate_recordset();other.state='done';self.env.flush_all()
        before=stored_payslip_code_totals(slip|other)
        self.assertIn(code,before[slip.id]);self.assertEqual(before[slip.id][code],0)
        self.assertEqual(before[other.id][code],-25)
        self.contract.wage=1200000
        self.assertEqual(stored_payslip_code_totals(slip|other),before)
        self.assertEqual(stored_payslip_totals(slip,code),{slip.id:0})

    def test_actual_movement_adapter_reads_stored_totals(self):
        slip,code=self.movement_slip(125)
        adapter=self.adapter()
        self.assertEqual(adapter.values(self.scope,slip,'bono_ok'),{slip.id:125})
        self.contract.wage=1200000
        self.assertEqual(adapter.values(self.scope,slip,'bono_ok'),{slip.id:125})
        self.assertFalse(slip.env.su)

    def test_actual_movement_adapter_rejects_hidden_lines(self):
        slip,code=self.movement_slip(125)
        self.env['ir.rule'].create({'name':'Private own book hidden line',
            'model_id':self.env['ir.model']._get_id('hr.payslip.line'),
            'domain_force':repr([('id','not in',slip.line_ids.ids)]),
            'perm_read':True,'perm_create':False,'perm_write':False,'perm_unlink':False})
        with self.assertRaises(AccessError):
            self.adapter().values(self.scope,slip.sudo(),'bono_ok')

    def test_native_registered_extractor_uses_original_code_map(self):
        slip,code=self.movement_slip(0)
        extractor=self.scope['step.remuneration.book.extractor']
        self.assertEqual(extractor._rule_totals(slip)[code],0)
        profile=self.env['step.remuneration.book.profile'].create({'name':'Private snapshot profile','code':'PRIVATE_SNAPSHOT'})
        mapping=self.env['step.remuneration.book.profile.line'].create({
            'profile_id':profile.id,'dt_code':'2101','source_type':'rule','rule_codes':code})
        self.assertEqual(extractor._resolve_values(slip,mapping,{}),{'2101':0})


@tagged('post_install','-at_install')
class FullBookInstall(PayrollContractMixin,TransactionCase):
    payroll_group='payroll.group_payroll_manager'

    def test_real_views_menus_and_actions(self):
        for model,view in [('step.hr.remuneration.book.wizard','view_hr_libro_remuneraciones_wizard_form_steps'),
                           ('step.remuneration.book.profile','view_remuneration_book_profile_form')]:
            record=self.env.ref('step_hr_remuneration_book.'+view)
            self.assertTrue(self.scope[model].get_view(view_id=record.id,view_type='form')['arch'])
        visible=self.scope['ir.ui.menu']._visible_menu_ids()
        self.assertIn(self.env.ref('step_hr_remuneration_book.menu_hr_payroll_libro_remuneraciones_steps').id,visible)
        actions=self.scope['hr.payslip']._steps_engine_actions()
        self.assertTrue(actions['payslips']);self.assertTrue(actions['batches'])
        for xmlid in actions.values():
            if xmlid:self.assertTrue(self.scope.ref(xmlid).exists())
        from odoo.addons.step_hr_remuneration_book.hooks import engine_alias_targets
        for name,target in engine_alias_targets(self.env).items():
            self.assertEqual(self.env.ref('step_hr_remuneration_book.'+name),target)

    def book_reference(self):
        from odoo.addons.step_hr_remuneration_book.tools import dt_book
        self.employee.identification_id='12345678-5'
        self.rule.amount_python_compute="result = inputs['PRIVATE_BONUS'].amount"
        zero=self.rule.copy({'name':'Private zero rule','code':'PRIVATE_ZERO','sequence':5,'amount_python_compute':'result = 0'})
        slip=self.slip(125);slip.compute_sheet();slip.state='done';self.env.flush_all()
        lines=[]
        for code in dt_book.REQUIRED_DT_CODES:
            values={'dt_code':code,'source_type':'rule','rule_codes':'PRIVATE_ZERO'}
            if code==dt_book.CODE_RUT:values={'dt_code':code,'source_type':'employee_rut'}
            elif code in (dt_book.CODE_WAGE,dt_book.CODE_TOTAL_TAXABLE,dt_book.CODE_TOTAL_INCOME,dt_book.CODE_NET):values['rule_codes']='LIQ'
            lines.append(Command.create(values))
        profile=self.env['step.remuneration.book.profile'].create({'name':'Private software report fixture',
            'code':'PRIVATE_FULL_BOOK','company_id':self.company.id,'line_ids':lines})
        profile.action_activate()
        self.company.remuneration_book_profile_id=profile
        wizard=self.scope['step.hr.remuneration.book.wizard'].create({'company_id':self.company.id,
            'month':str(slip.date_from.month),'year':slip.date_from.year,'mode':'full'})
        return slip,wizard

    def test_real_consolidated_outputs(self):
        from odoo.addons.step_hr_remuneration_book.tools import dt_book
        from odoo.addons.step_hr_remuneration_book.tools.xlsx_book import build_workbook
        slip,wizard=self.book_reference()
        dataset=wizard.build_dataset()
        self.assertFalse(dataset.errors,[issue.code for issue in dataset.errors])
        self.assertEqual(len(dataset.lines),1)
        self.assertEqual(dataset.lines[0].values[dt_book.CODE_NET],125)
        import io
        stream=io.BytesIO();build_workbook(stream,dataset)
        self.assertTrue(stream.getvalue().startswith(b'PK'))
        self.assertIn('/step/payroll/remuneration-book/xlsx',wizard.action_download_xlsx()['url'])
        action=wizard.action_download_pdf();self.assertEqual(action['report_name'],'step_hr_remuneration_book.consolidated_book')
        html,_=self.scope['ir.actions.report']._render_qweb_html('step_hr_remuneration_book.action_report_consolidated_book',wizard.ids)
        self.assertIn(b'Private API employee',html)
        if self.env['ir.module.module'].search_count([('name','=','payroll'),('state','=','installed')]):
            self.assertFalse(wizard.official_csv_available)
            with self.assertRaisesRegex(UserError,'certific'):wizard.action_download_official_csv()
        self.assertFalse(self.scope.su)

    def test_pdf_scope_requires_one_readable_wizard(self):
        slip,wizard=self.book_reference()
        report=self.scope['report.step_hr_remuneration_book.consolidated_book']
        for ids in ([],wizard.ids+wizard.ids):
            with self.assertRaises(UserError):report._get_report_values(ids)
        foreign=wizard.with_env(self.env).copy()  # Admin owns this private transient, not the reporting actor.
        self.assertNotEqual(foreign.create_uid,self.scope.user)
        with self.assertRaises(AccessError):report._get_report_values(foreign.ids)
        self.env['ir.rule'].create({'name':'Private PDF hidden salary',
            'model_id':self.env['ir.model']._get_id('hr.payslip.line'),
            'domain_force':repr([('id','not in',slip.line_ids.ids)]),
            'perm_read':True,'perm_write':False,'perm_create':False,'perm_unlink':False})
        with self.assertRaises(AccessError):report._get_report_values(wizard.ids)

    def test_pdf_template_preserves_zero_and_negative_amounts(self):
        from odoo.addons.step_hr_remuneration_book.report.remuneration_book_report import format_amount
        self.assertEqual(format_amount(0),'0')
        self.assertEqual(format_amount(-125),'-125')
        self.assertEqual(format_amount(None),'')
        slip,wizard=self.book_reference()
        html,_=self.scope['ir.actions.report']._render_qweb_html(
            'step_hr_remuneration_book.action_report_consolidated_book',wizard.ids)
        from lxml import html as etree
        cells=[node.text_content().strip() for node in etree.fromstring(html).xpath('//td')]
        self.assertIn('0',cells);self.assertIn('125',cells)

    def test_partial_user_cannot_export_full_book(self):
        from odoo.addons.step_payroll_contracts.access import payroll_role_group
        user=self.env['res.users'].with_context(no_reset_password=True).create({'name':'Private book partial user',
            'login':'private-fullbook-partial','company_id':self.company.id,'company_ids':[Command.set(self.company.ids)],
            'groups_id':[Command.set([self.env.ref('base.group_user').id,payroll_role_group(self.env,'user').id])]})
        scope=api.Environment(self.env.cr,user.id,dict(self.scope.context),su=False)
        wizard=scope['step.hr.remuneration.book.wizard'].create({'company_id':self.company.id,'mode':'full'})
        self.assertFalse(wizard.user_has_full_access())
        with self.assertRaises(UserError):wizard._step_check_access()
        self.assertNotIn(self.env.ref('step_hr_remuneration_book.menu_hr_payroll_libro_remuneraciones_steps').id,
                         scope['ir.ui.menu']._visible_menu_ids())

    def test_engine_alias_retirement_preserves_records(self):
        from odoo.addons.step_hr_remuneration_book.hooks import engine_alias_targets,uninstall_hook,ensure_engine_aliases
        targets=engine_alias_targets(self.env)
        uninstall_hook(self.env)
        for name,record in targets.items():
            self.assertTrue(record.exists())
            self.assertFalse(self.env.ref('step_hr_remuneration_book.'+name,raise_if_not_found=False))
        ensure_engine_aliases(self.env)
        for name,record in targets.items():self.assertEqual(self.env.ref('step_hr_remuneration_book.'+name),record)


@tagged('post_install','-at_install')
class FullBookHttp(FullBookInstall,HttpCase):
    """Real sessions and routes; no replacement generator, response or payroll model."""

    def login_owner(self):
        import uuid
        password=uuid.uuid4().hex
        self.scope.user.sudo().with_context(no_reset_password=True).write({'password':password})
        self.authenticate(self.scope.user.login,password)

    def change_url(self,url,**updates):
        from urllib.parse import urlsplit,parse_qsl,urlencode,urlunsplit
        parts=urlsplit(url);query=dict(parse_qsl(parts.query));query.update(updates)
        return urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(query),parts.fragment))

    def test_signed_xlsx_response_and_audit(self):
        import io,zipfile
        slip,wizard=self.book_reference();self.login_owner()
        logs=self.scope['step.remuneration.book.log']
        domain=[('company_id','=',self.company.id),('user_id','=',self.scope.uid),('output','=','xlsx')]
        before=logs.search_count(domain)
        response=self.url_open(wizard.action_download_xlsx()['url'])
        self.assertEqual(response.status_code,200)
        self.assertIn('spreadsheetml',response.headers.get('Content-Type',''))
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertIn(b'<v>125</v>',archive.read('xl/worksheets/sheet1.xml'))
            self.assertIn(b'Private API employee',archive.read('xl/sharedStrings.xml'))
        self.env.invalidate_all()
        self.assertEqual(logs.search_count(domain),before+1)
        self.assertEqual(logs.search(domain,order='id desc',limit=1).user_id,self.scope.user)

    def test_tampered_links_rejected(self):
        slip,wizard=self.book_reference();self.login_owner()
        url=wizard.action_download_xlsx()['url']
        for values in ({'token':'invalid'},{'exp':'0'},{'company_id':str(self.env.company.id)},
                       {'date_to':wizard.date_from.isoformat()}):
            response=self.url_open(self.change_url(url,**values))
            self.assertEqual(response.status_code,404)
            self.assertFalse(response.content.startswith(b'PK'))

    def test_foreign_owner_rejected(self):
        import uuid
        from odoo.addons.step_payroll_contracts.access import payroll_role_group
        slip,wizard=self.book_reference();url=wizard.action_download_xlsx()['url']
        password=uuid.uuid4().hex
        other=self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private book other manager','login':'private-book-other-owner','password':password,
            'company_id':self.company.id,'company_ids':[Command.set(self.company.ids)],
            'groups_id':[Command.set([self.env.ref('base.group_user').id,payroll_role_group(self.env,'manager').id])]})
        self.authenticate(other.login,password)
        response=self.url_open(url);self.assertEqual(response.status_code,404)
        self.assertFalse(response.content.startswith(b'PK'))

    def test_hidden_line_denied_without_report(self):
        slip,wizard=self.book_reference();self.login_owner()
        self.env['ir.rule'].create({'name':'Private HTTP hidden salary',
            'model_id':self.env['ir.model']._get_id('hr.payslip.line'),
            'domain_force':repr([('id','not in',slip.line_ids.ids)]),
            'perm_read':True,'perm_write':False,'perm_create':False,'perm_unlink':False})
        response=self.url_open(wizard.action_download_xlsx()['url'])
        self.assertEqual(response.status_code,404);self.assertFalse(response.content.startswith(b'PK'))
        self.env.invalidate_all()
        record=self.scope['step.remuneration.book.log'].search([
            ('company_id','=',self.company.id),('output','=','xlsx')],order='id desc',limit=1)
        self.assertEqual((record.result,record.detail),('blocked','salary_access'))

    def test_official_csv_policy_over_http(self):
        slip,wizard=self.book_reference();self.login_owner()
        url=wizard._download_url('/step/payroll/remuneration-book/official-csv','csv')['url']
        self.assertEqual(self.url_open(self.change_url(url,token='invalid')).status_code,404)
        if self.env['ir.module.module'].search_count([('name','=','payroll'),('state','=','installed')]):
            response=self.url_open(url);self.assertEqual(response.status_code,409)
            self.assertIn('certific',response.text)
            self.assertNotIn('text/csv',response.headers.get('Content-Type',''))

    def test_dashboard_rpc_uses_real_engine_actions(self):
        import json
        slip,wizard=self.book_reference();self.login_owner()
        batch=self.scope['hr.payslip.run'].create({'name':'Private HTTP batch','company_id':self.company.id,
            'date_start':wizard.date_from,'date_end':wizard.date_to})
        payload={'jsonrpc':'2.0','method':'call','id':1,'params':{'model':'hr.payslip',
            'method':'get_steps_payroll_dashboard','args':[],
            'kwargs':{'period':wizard.date_from.strftime('%Y-%m'),'context':{'allowed_company_ids':self.company.ids}}}}
        response=self.url_open('/web/dataset/call_kw/hr.payslip/get_steps_payroll_dashboard',
            data=json.dumps(payload),headers={'Content-Type':'application/json'})
        data=response.json();self.assertNotIn('error',data)
        result=data['result'];self.assertEqual((result['gross'],result['net']),(125,125))
        self.assertTrue(result['engine_actions']['payslips']);self.assertTrue(result['book_available'])
        self.assertIn(batch.id,[row['id'] for row in result['recent_batches']])
        self.assertFalse(result['contributions']['available'])

    def _pdf_asset_sidecar(self, documents):
        """Serve exact prefetched runtime assets, avoiding nested test-cursor deadlocks."""
        import re,threading,hashlib
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        from urllib.parse import urljoin,urlsplit
        from lxml import html as etree
        origin=self.base_url();cache={};missing=[];unused_font_urls=set();todo=[]
        for html in documents:
            todo.extend(etree.fromstring(html).xpath('//link[@href]/@href | //script[@src]/@src | //img[@src]/@src'))
        # Native website requests scope asset URLs by website. Prefetch the exact
        # scoped PDF URLs too: _prepare_html outside HTTP produces unscoped URLs.
        scopes={match.group(1) for link in todo
                if (match:=re.match(r'^/web/assets/([0-9]+)/[0-9a-f]+/',urlsplit(link).path))}
        for link in list(todo):
            match=re.match(r'^/web/assets/([0-9a-f]+/[^/]+)$',urlsplit(link).path)
            if match:todo.extend('/web/assets/'+scope+'/'+match.group(1) for scope in scopes)
        while todo:
            link=todo.pop()
            if link.startswith('data:'):continue
            parsed=urlsplit(urljoin(origin,link))
            self.assertEqual(parsed.netloc,urlsplit(origin).netloc,'Only private runtime assets may be prefetched')
            key=parsed.path
            if key in cache:continue
            response=self.url_open(key+('?' + parsed.query if parsed.query else ''))
            self.assertIn(response.status_code,(200,404),(key,response.status_code))
            cache[key]=(response.content,response.headers.get('Content-Type','application/octet-stream'),response.status_code)
            if cache[key][2]==200 and 'text/css' in cache[key][1]:
                css=response.content.decode('utf-8')
                for raw in re.findall(r'url\(\s*([^)]*?)\s*\)',css):
                    value=raw.strip('\"\' ')
                    if value and not value.startswith('data:'):
                        host=urlsplit(value).netloc
                        if host:
                            self.assertEqual(host,'fonts.odoocdn.com','Unknown external runtime asset')
                            unused_font_urls.add(value)
                        else:todo.append(urljoin(key,value))
        self.assertTrue(cache)
        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler):
                key=urlsplit(handler.path).path
                if key not in cache:
                    missing.append(key);handler.send_error(404);return
                payload,mime,status=cache[key]
                if status!=200:missing.append(key)
                handler.send_response(status)
                handler.send_header('Content-Type',mime);handler.send_header('Content-Length',str(len(payload)))
                handler.end_headers();handler.wfile.write(payload)
            def log_message(handler,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        return server,thread,missing,{key:hashlib.sha256(value[0]).hexdigest() for key,value in cache.items()},sorted(unused_font_urls)

    def test_actual_pdf_binary_and_employee_sheets(self):
        import io,json,hashlib
        from pathlib import Path
        from urllib.parse import urlencode
        from PyPDF2 import PdfFileReader
        from odoo import tools
        slip,wizard=self.book_reference();self.login_owner()
        self.env['ir.config_parameter'].sudo().set_param('report.url',self.base_url())
        before=stored_payslip_totals(slip,'LIQ');proofs=[]
        for name,output,dimensions in [('consolidated_book','pdf',(1008,612)),
                                       ('employee_sheets','sheets',(595,842))]:
            context={'force_report_rendering':True,'allowed_company_ids':self.company.ids}
            suffix='step_hr_remuneration_book.%s/%s?'%(name,wizard.id)+urlencode({'context':json.dumps(context)})
            html=self.url_open('/report/html/'+suffix)
            self.assertEqual(html.status_code,200)
            action=self.scope.ref('step_hr_remuneration_book.action_report_'+name)
            bodies,ids,header,footer,paper=action._prepare_html(html.content,report_model=wizard._name)
            server,thread,missing,assets,font_urls=self._pdf_asset_sidecar([html.content,*bodies,header,footer])
            domain=[('company_id','=',self.company.id),('output','=',output)]
            self.env.invalidate_all()
            count=self.scope['step.remuneration.book.log'].search_count(domain)
            self.env['ir.config_parameter'].sudo().set_param('report.url','http://127.0.0.1:%s'%server.server_port)
            try:
                response=self.url_open('/report/pdf/'+suffix,timeout=120)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)
                self.env['ir.config_parameter'].sudo().set_param('report.url',self.base_url())
            self.assertFalse(missing,missing)
            self.assertEqual(response.status_code,200)
            self.assertIn('application/pdf',response.headers.get('Content-Type',''))
            self.assertEqual(response.headers.get('Cache-Control'),'no-store')
            self.assertTrue(response.content.startswith(b'%PDF-'))
            reader=PdfFileReader(io.BytesIO(response.content));self.assertGreater(reader.getNumPages(),0)
            page=reader.getPage(0);width,height=map(float,(page.mediaBox.getWidth(),page.mediaBox.getHeight()))
            self.assertAlmostEqual(width,dimensions[0],delta=2);self.assertAlmostEqual(height,dimensions[1],delta=2)
            self.env.invalidate_all()
            logs=self.scope['step.remuneration.book.log'].search(domain,order='id desc')
            self.assertEqual(len(logs),count+1);self.assertEqual(logs[0].user_id,self.scope.user)
            self.assertEqual(logs[0].result,'ok');self.assertEqual(stored_payslip_totals(slip,'LIQ'),before)
            directory=Path(tools.config['data_dir']).parent/'pdf-evidence'
            if str(directory).startswith('/opt/steps-validation/community-payroll-book-'):
                directory.mkdir(exist_ok=True);(directory/(name+'.pdf')).write_bytes(response.content)
                proofs.append({'report':name,'output':output,'pages':reader.getNumPages(),
                    'width':width,'height':height,'sha256':hashlib.sha256(response.content).hexdigest(),
                    'normal_actor':not self.scope.su,'single_audit':True,'history_preserved':True,
                    'asset_source':'exact_runtime_prefetch','asset_sha256':assets,'missing_assets':missing,
                    'unused_cdn_font_declarations':font_urls})
        if proofs:
            (directory/'pdf-proof.json').write_text(json.dumps(proofs,indent=2),encoding='utf-8')
