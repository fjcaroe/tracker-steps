"""Exercise the original operational app against real Community models."""
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class HrCommunityCase(TransactionCase):
    def test_original_tracker_relations_and_forms(self):
        for model, relation in [('step.tracker.machine','fleet.vehicle'),
                                ('step.tracker.driver','hr.employee')]:
            field='vehicle_id' if relation=='fleet.vehicle' else 'employee_id'
            self.assertEqual(self.env[model]._fields[field].comodel_name,relation)
        for model in ('step.tracker','step.tracker.machine','step.tracker.driver',
                      'step.tracker.activity','step.tracker.labor','step.tracker.implement',
                      'step.tracker.field','step.tracker.session','step.tracker.work_order','step.history'):
            self.assertTrue(self.env[model].get_view(view_type='form')['arch'])
        self.assertEqual(self.env.ref('step_hr.action_step_activities_dashboard').tag,'step_hr.activities_dashboard')

    def test_native_bank_type_and_real_optional_payroll(self):
        bridge=self.env['ir.module.module'].search_count([('name','=','step_hr_payroll_bridge'),('state','=','installed')])
        self.assertEqual(self.env['res.partner']._fields['duplicate_bank_partner_ids'].type,
                         'boolean' if bridge else 'many2many')
        self.assertEqual('net_liquido' in self.env['hr.payslip']._fields if 'hr.payslip' in self.env else False,bool(bridge))
        self.assertEqual(hasattr(self.env['step.tarja'],'envio_nomina'),bool(bridge))

    def test_original_root_and_restricted_history(self):
        self.assertTrue(self.env.ref('step_hr.menu_step_hr_root').active)
        self.assertFalse(self.env.ref('step_agriculture_core.menu_agriculture_core').active)
        self.assertFalse(self.env.ref('step_labor_operations_core.menu_labor_operations').active)
        self.assertEqual(self.env.ref('step_hr.step_history').groups_id,
                         self.env.ref('step_hr.permin_step_history'))

    def test_portal_cannot_read_tracker_or_history(self):
        portal=self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'HR portal fixture','login':'hr-community-portal-fixture',
            'groups_id':[Command.set(self.env.ref('base.group_portal').ids)]})
        for model in ('step.tracker','step.tracker.machine','step.tracker.driver','step.history'):
            with self.subTest(model=model), self.assertRaises(AccessError):
                self.env[model].with_user(portal).check_access('read')
