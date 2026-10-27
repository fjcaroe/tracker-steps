from odoo.tests import TransactionCase, tagged
from ..hooks import pre_init_hook, post_init_hook, FIELDS, VIEWS


@tagged('post_install', '-at_install')
class HrPayrollBridgeCase(TransactionCase):
    def test_aliases_and_native_field_ids_survive_repeated_adoption(self):
        before={name:self.env.ref('step_hr.'+name).id for name in VIEWS}
        fields={model:{name:self.env['ir.model.fields']._get(model,name).id for name in names}
                for model,names in FIELDS.items()}
        for _ in range(2):pre_init_hook(self.env);post_init_hook(self.env)
        for name in VIEWS:
            self.assertEqual(self.env.ref('step_hr.'+name).id,before[name])
            self.assertEqual(self.env.ref('step_hr_payroll_bridge.'+name).id,before[name])
        for model,names in fields.items():
            for name,identifier in names.items():
                self.assertEqual(self.env['ir.model.fields']._get(model,name).id,identifier)
        self.assertEqual(self.env['res.partner']._fields['duplicate_bank_partner_ids'].type,'boolean')

    def test_actual_payroll_models_relations_and_inherited_forms(self):
        for name,comodel in [('payslip_run_id','hr.payslip.run'),('struct_id','hr.payroll.structure')]:
            self.assertEqual(self.env['hr.salary.custom']._fields[name].comodel_name,comodel)
            self.assertIn(comodel,self.env.registry.models)
        self.assertTrue(self.env['hr.payslip'].get_view(self.env.ref('step_hr.hr_payslip_step_view_tree').id,'list')['arch'])
        self.assertTrue(self.env['step.tarja'].get_view(self.env.ref('step_hr.view_step_tarja_form').id,'form')['arch'])

    def test_hr_upgrade_without_required_real_bridge_is_rejected(self):
        from odoo.exceptions import UserError
        from odoo.addons.step_hr.migration_guard import require_payroll_bridge
        require_payroll_bridge(self.env.cr)
        self.env.cr.execute("SELECT state FROM ir_module_module WHERE name='step_hr_payroll_bridge'")
        original=self.env.cr.fetchone()[0]
        try:
            self.env.cr.execute("UPDATE ir_module_module SET state='uninstalled' WHERE name='step_hr_payroll_bridge'")
            with self.assertRaises(UserError):require_payroll_bridge(self.env.cr)
        finally:
            self.env.cr.execute("UPDATE ir_module_module SET state=%s WHERE name='step_hr_payroll_bridge'",[original])
