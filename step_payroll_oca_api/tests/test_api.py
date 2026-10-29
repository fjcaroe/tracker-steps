from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin


@tagged('post_install','-at_install')
class OcaApiCase(PayrollContractMixin,TransactionCase):
    payroll_group='payroll.group_payroll_manager'
    oca=True

    def test_stored_components_keep_rounded_total_and_original_factors(self):
        PayrollContractMixin.test_stored_components_keep_rounded_total_and_original_factors(self)

    def test_stored_components_enforce_field_and_complete_line_access(self):
        PayrollContractMixin.test_stored_components_enforce_field_and_complete_line_access(self)

    def test_stored_components_retain_ambiguous_rules_as_separate_lines(self):
        PayrollContractMixin.test_stored_components_retain_ambiguous_rules_as_separate_lines(self)

    def test_worked_day_master_is_available_in_normal_payroll_form(self):
        from lxml import etree
        arch=etree.fromstring(self.scope['hr.payslip'].get_view(view_type='form')['arch'])
        for subview in ('list','form'):
            self.assertTrue(arch.xpath("//field[@name='worked_days_line_ids']/"+subview+"//field[@name='work_entry_type_id']"))
            self.assertEqual(arch.xpath("//field[@name='worked_days_line_ids']/"+subview+"//field[@name='code']/@readonly"),['work_entry_type_id'])
        kind=self.scope['hr.work.entry.type'].create({'name':'Private form day','code':'PRIVATE_FORM_DAY'})
        line=self.scope['hr.payslip.worked_days'].new({'work_entry_type_id':kind.id})
        line._onchange_type_code()
        self.assertEqual(line.code,kind.code)

    def test_typed_worked_day_code_keeps_master_and_historical_identity(self):
        slip=self.slip()
        kind=self.scope['hr.work.entry.type'].create({'name':'Private typed day','code':'PRIVATE_TYPED_DAY'})
        line=self.scope['hr.payslip.worked_days'].create({'name':'Private typed day','payslip_id':slip.id,
            'contract_id':self.contract.id,'work_entry_type_id':kind.id,'number_of_days':1,'number_of_hours':8})
        self.assertEqual(line.code,kind.code)
        for operation in [lambda:line.write({'code':'WRONG'}),lambda:line.write({'work_entry_type_id':False}),
                          lambda:kind.write({'code':'CHANGED'})]:
            with self.assertRaises(ValidationError),self.env.cr.savepoint():operation()
        slip.state='done';before=line.read(['id','code','work_entry_type_id','number_of_days','number_of_hours'])
        with self.assertRaises(UserError):line.write({'code':kind.code})
        self.assertEqual(line.read(['id','code','work_entry_type_id','number_of_days','number_of_hours']),before)

    def test_legacy_worked_day_code_is_not_reconstructed_on_read(self):
        slip=self.slip()
        line=self.scope['hr.payslip.worked_days'].create({'name':'Private legacy day','payslip_id':slip.id,
            'contract_id':self.contract.id,'code':'PRIVATE_LEGACY_DAY','number_of_days':1,'number_of_hours':8})
        before=line.read(['id','code','work_entry_type_id'])
        self.assertFalse(line.work_entry_type_id)
        self.assertEqual(line.read(['id','code','work_entry_type_id']),before)

    def test_monthly_worked_day_basis_uses_real_rows_and_missing_day_is_zero(self):
        PayrollContractMixin.test_monthly_worked_day_basis_uses_real_rows_and_missing_day_is_zero(self)

    def test_reference_selection_preserves_zero_cases_and_prefers_closed_positive(self):
        PayrollContractMixin.test_reference_selection_preserves_zero_cases_and_prefers_closed_positive(self)

    def test_duplicate_code_category_effects_match_native_observations(self):
        PayrollContractMixin.test_duplicate_code_category_effects_match_native_observations(self)

    def test_paid_or_validated_slip_is_never_recomputed(self):
        for state,paid in [('done',False),('draft',True)]:
            slip=self.slip();slip.compute_sheet();slip.write({'state':state,'paid':paid})
            self.env.flush_all()
            query='SELECT to_jsonb(t) FROM hr_payslip_line t WHERE slip_id=%s ORDER BY id'
            self.env.cr.execute(query,(slip.id,));before=self.env.cr.fetchall()
            with self.assertRaises(UserError):slip.compute_sheet()
            self.env.flush_all()
            self.env.cr.execute(query,(slip.id,))
            self.assertEqual(self.env.cr.fetchall(),before)

    def test_rule_foreign_key_updates_real_oca_membership(self):
        self.assertIn(self.rule,self.structure.rule_ids)
        other=self.structure.copy({'name':'Other private structure','rule_ids':[Command.clear()]})
        self.rule.struct_id=other
        self.assertNotIn(self.rule,self.structure.rule_ids)
        self.assertIn(self.rule,other.rule_ids)

    def test_input_structure_and_code_constraints(self):
        slip=self.slip()
        other=self.structure.copy({'name':'Other input structure','rule_ids':[Command.clear()]})
        with self.assertRaises(ValidationError),self.env.cr.savepoint():
            slip.input_line_ids.code='WRONG_CODE'
        kind=self.input_type.copy({'code':'PRIVATE_OTHER','struct_ids':[Command.set(other.ids)]})
        with self.assertRaises(ValidationError),self.env.cr.savepoint():
            self.scope['hr.payslip.input'].create({'payslip_id':slip.id,'contract_id':self.contract.id,
                'input_type_id':kind.id,'amount':1})

    def test_ytd_reads_actual_stored_values_and_rejects_unknown_fields(self):
        slip=self.slip();slip.compute_sheet()
        self.assertEqual(slip._get_line_values(['LIQ'],['ytd'])['LIQ'][slip.id]['ytd'],slip.line_ids.filtered(lambda line:line.code=='LIQ').total)
        with self.assertRaises(UserError):slip._get_line_values(['LIQ'],['unverified'])

    def test_used_input_type_keeps_historical_scope(self):
        self.slip()
        for values in ({'code':'CHANGED'},{'country_id':self.env.ref('base.cl').id},{'struct_ids':[Command.clear()]}):
            with self.assertRaises(ValidationError),self.env.cr.savepoint():
                self.input_type.write(values)

    def test_primary_rule_membership_cannot_diverge(self):
        with self.assertRaises(ValidationError),self.env.cr.savepoint():
            self.structure.write({'rule_ids':[Command.unlink(self.rule.id)]})

    def test_real_engine_typed_input_and_liquid_code(self):
        PayrollContractMixin.test_real_engine_typed_input_and_liquid_code(self)

    def test_line_values_missing_codes_and_multi_slip_sum(self):
        PayrollContractMixin.test_line_values_missing_codes_and_multi_slip_sum(self)

    def test_line_values_reads_do_not_change_validated_lines(self):
        PayrollContractMixin.test_line_values_reads_do_not_change_validated_lines(self)

    def test_rules_receive_real_record_and_mapping_get(self):
        PayrollContractMixin.test_rules_receive_real_record_and_mapping_get(self)

    def test_actual_accounting_entry_balances(self):
        PayrollContractMixin.test_actual_accounting_entry_balances(self)

    def test_portal_cannot_read_salary_lines(self):
        PayrollContractMixin.test_portal_cannot_read_salary_lines(self)

    def test_duplicate_typed_inputs_are_not_silently_overwritten(self):
        for typed in (False,):
            slip=self.slip()
            if typed:
                slip.input_line_ids.copy({'payslip_id':slip.id})
            else:
                self.scope['hr.payslip.input'].create({'name':'Legacy same code','code':'PRIVATE_BONUS',
                    'payslip_id':slip.id,'contract_id':self.contract.id,'amount':999})
            with self.assertRaises(UserError):slip.compute_sheet()
            self.assertFalse(slip.line_ids)
            self.assertEqual(len(slip.input_line_ids),2)

    def test_payroll_reader_cannot_change_input_master(self):
        actor=self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private payroll reader','login':'private-payroll-api-reader',
            'company_id':self.company.id,'company_ids':[Command.set(self.company.ids)],
            'groups_id':[Command.set([self.env.ref('base.group_user').id,self.env.ref('payroll.group_payroll_user').id])]})
        kind=self.input_type.with_user(actor)
        self.assertEqual(kind.read(['code'])[0]['code'],'PRIVATE_BONUS')
        with self.assertRaises(AccessError):kind.write({'name':'Forbidden edit'})

    def test_slip_structure_cannot_invalidate_input_type(self):
        slip=self.slip()
        other=self.structure.copy({'name':'Unrelated private structure','rule_ids':[Command.clear()]})
        with self.assertRaises(ValidationError),self.env.cr.savepoint():
            slip.struct_id=other
        self.assertEqual(slip.struct_id,self.structure)

    def test_repeated_input_amounts_aggregate_without_changing_rows(self):
        PayrollContractMixin.test_repeated_input_amounts_aggregate_without_changing_rows(self)

    def test_repeated_input_nonlinear_rule_is_evaluated_per_line(self):
        PayrollContractMixin.test_repeated_input_nonlinear_rule_is_evaluated_per_line(self)

    def test_quantities_rates_and_categories_preserve_clp_rounding(self):
        PayrollContractMixin.test_quantities_rates_and_categories_preserve_clp_rounding(self)

    def test_fractional_negative_rate_uses_real_engine(self):
        PayrollContractMixin.test_fractional_negative_rate_uses_real_engine(self)

    def test_actual_work_entries_types_and_domain(self):
        PayrollContractMixin.test_actual_work_entries_types_and_domain(self)

    def test_calendar_timezone_clips_work_entry_at_payroll_boundary(self):
        PayrollContractMixin.test_calendar_timezone_clips_work_entry_at_payroll_boundary(self)

    def test_chile_concept_rounding_matches_known_salary_cases(self):
        PayrollContractMixin.test_chile_concept_rounding_matches_known_salary_cases(self)

    def test_chile_final_quantity_rate_and_signed_halves(self):
        PayrollContractMixin.test_chile_final_quantity_rate_and_signed_halves(self)

    def test_structure_configuration_form_and_work_entry_opt_in(self):
        from lxml import etree
        view=self.scope['hr.payroll.structure'].get_view(self.scope.ref('payroll.hr_payroll_structure_view_form').id,'form')
        form=etree.fromstring(view['arch'])
        for field in ('type_id','use_work_entries','step_clp_concept_rounding'):
            self.assertTrue(form.xpath("//field[@name='%s']"%field))
        self.structure.use_work_entries=True
        self.work_calendar()
        slip=self.slip()
        self.assertEqual(slip.get_worked_day_lines(self.contract,slip.date_from,slip.date_to),[])

    def test_type_rounding_and_no_work_entry_side_effects(self):
        slip=self.slip()
        kind=self.scope['hr.work.entry.type'].create({'name':'Private rounding type','code':'PAPI_ROUND','round_days':'HALF','round_days_type':'UP'})
        self.assertEqual(slip._round_days(kind,0.3),0.5)
        kind.round_days_type='DOWN'
        self.assertEqual(slip._round_days(kind,0.3),0)
        kind.round_days_type='HALF-UP'
        self.assertEqual(slip._round_days(kind,0.25),0.5)

    def test_clp_policy_keeps_earlier_period_and_validated_states(self):
        from datetime import date
        self.structure.step_clp_concept_rounding=True
        for month in (9,10):
            for state in ('draft','verify','done','cancel'):
                slip=self.slip()
                slip.write({'date_from':date(2026,month,1),'date_to':date(2026,month,28)})
                slip.state=state
                self.assertEqual(slip._get_payslip_line_total(10.6,1,100,self.rule),11 if month==10 and state in ('draft','verify') else 10.6)

    def test_work_hours_do_not_elevate_company_access(self):
        company=self.env.ref('base.main_company')
        actor=self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Private other company HR','login':'private-payroll-other-company',
            'company_id':company.id,'company_ids':[Command.set(company.ids)],
            'groups_id':[Command.set([self.env.ref('base.group_user').id,self.env.ref('hr.group_hr_manager').id])]})
        with self.assertRaises(AccessError):
            self.contract.with_user(actor).with_context(allowed_company_ids=company.ids).get_work_hours(self.contract.date_start,self.contract.date_start)

    def test_work_entry_payroll_refreshes_actual_days_without_replacing_ids(self):
        from datetime import datetime,time,timedelta
        from odoo import fields
        self.work_calendar();self.structure.use_work_entries=True
        first=fields.Date.today().replace(day=1);monday=first+timedelta(days=(-first.weekday())%7)
        kind=self.scope['hr.work.entry.type'].create({'name':'Private payroll attendance','code':'PAPI_AUTO'})
        entry=self.scope['hr.work.entry'].create({'name':'Private actual payroll entry','employee_id':self.employee.id,
            'company_id':self.company.id,'contract_id':self.contract.id,'work_entry_type_id':kind.id,
            'date_start':datetime.combine(monday,time(8)),'date_stop':datetime.combine(monday,time(12))})
        self.rule.amount_python_compute="result = worked_days.get('PAPI_AUTO').number_of_hours"
        slip=self.slip();slip.compute_sheet()
        ids=slip.worked_days_line_ids.ids
        self.assertEqual(slip.worked_days_line_ids.work_entry_type_id,kind)
        self.assertEqual(slip._get_line_values(['LIQ'])['LIQ'][slip.id]['total'],4)
        entry.date_stop=datetime.combine(monday,time(10))
        slip.compute_sheet()
        self.assertEqual(slip.worked_days_line_ids.ids,ids)
        self.assertEqual(slip.worked_days_line_ids.number_of_hours,2)
        self.assertEqual(slip._get_line_values(['LIQ'])['LIQ'][slip.id]['total'],2)

    def test_empty_work_entry_payroll_never_assumes_full_wage(self):
        self.structure.use_work_entries=True
        slip=self.slip()
        with self.assertRaises(UserError):slip.compute_sheet()
        self.assertFalse(slip.worked_days_line_ids)
        self.assertFalse(slip.line_ids)

    def test_out_of_contract_days_use_original_calendar(self):
        PayrollContractMixin.test_out_of_contract_days_use_original_calendar(self)

    def test_stored_essential_distinct_rule_identities_are_not_summed(self):
        PayrollContractMixin.test_stored_essential_distinct_rule_identities_are_not_summed(self)

    def test_stored_same_rule_rows_remain_additive_and_stable(self):
        PayrollContractMixin.test_stored_same_rule_rows_remain_additive_and_stable(self)

    def test_stored_nonessential_distinct_rules_keep_additive_contract(self):
        PayrollContractMixin.test_stored_nonessential_distinct_rules_keep_additive_contract(self)
