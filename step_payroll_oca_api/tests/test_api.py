from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin


@tagged('post_install','-at_install')
class OcaApiCase(PayrollContractMixin,TransactionCase):
    payroll_group='payroll.group_payroll_manager'
    oca=True

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

    def test_ytd_is_explicitly_unsupported(self):
        with self.assertRaises(UserError):self.slip()._get_line_values(['LIQ'],['ytd'])

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
