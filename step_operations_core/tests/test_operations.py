from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged, Form
from ..ownership import FIELDS, RECORDS
from ..hooks import adopt_legacy_records, preserve_legacy_xmlids


@tagged('post_install', '-at_install')
class OperationsCoreCase(TransactionCase):
    def test_metadata_aliases_are_original_records(self):
        for name, model in RECORDS.items():
            with self.subTest(xmlid=name):
                legacy = self.env.ref('step_hr.' + name)
                self.assertEqual(legacy, self.env.ref('step_operations_core.' + name))
                self.assertEqual(legacy._name, model)
        before = {name: self.env.ref('step_hr.' + name).id for name in RECORDS}
        adopt_legacy_records(self.env)
        preserve_legacy_xmlids(self.env)
        self.assertEqual(before, {name: self.env.ref('step_hr.' + name).id for name in RECORDS})

    def test_native_employee_costs_and_private_access(self):
        hr_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Operational HR fixture', 'login': 'operational-hr-fixture',
            'company_id': self.env.company.id, 'company_ids': [Command.set(self.env.company.ids)],
            'groups_id': [Command.set([self.env.ref('base.group_user').id, self.env.ref('hr.group_hr_user').id])],
        })
        schedule = self.env['step.work.schedule'].create({'name': 'Operations shift', 'lunes': 8})
        contractor = self.env['res.partner'].create({'name': 'Operations contractor', 'step_contra': True})
        employee = self.env['hr.employee'].with_user(hr_user).create({
            'name': 'Operations employee', 'company_id': self.env.company.id,
            'step_work_schedule': schedule.id, 'is_propio': True, 'is_contratista': True,
            'contratista_id': contractor.id, 'costo_empresa': 123.45, 'costo_contratista': 67.89,
        })
        self.assertEqual(employee.step_work_schedule, schedule)
        self.assertEqual(employee.contratista_id, contractor)
        self.assertEqual(employee.costo_empresa, 123.45)
        self.assertEqual(employee.costo_contratista, 67.89)
        self.assertEqual(employee.cost_currency_id, self.env.company.currency_id)
        self.assertTrue(employee.get_view(self.env.ref('step_hr.step_view_hr_employee_form').id, 'form')['arch'])
        portal = self.env['res.users'].create({'name': 'Operations portal', 'login': 'operations-portal-fixture',
            'groups_id': [Command.set([self.env.ref('base.group_portal').id])]})
        with self.assertRaises(AccessError):
            employee.with_user(portal).check_access('read')

    def test_generic_task_remains_native_and_nullable(self):
        task = self.env['project.task'].create({'name': 'Generic Community task', 'num_op': 'QA-OPS'})
        self.assertFalse(task.variedad_id)
        self.assertFalse(task.grupo_variedad_id)
        self.assertEqual(task.num_op, 'QA-OPS')
        view = self.env.ref('step_hr.step_project_task_view_inherit')
        self.assertIn('num_op', task.get_view(view.id, 'form')['arch'])
        self.env.cr.execute("SELECT is_nullable FROM information_schema.columns WHERE table_name='project_task' "
                            "AND column_name IN ('variedad_id','grupo_variedad_id') ORDER BY column_name")
        self.assertEqual(self.env.cr.fetchall(), [('YES',), ('YES',)])

    def test_alias_conflict_is_rejected(self):
        alias = self.env['ir.model.data'].search([('module', '=', 'step_operations_core'),
                                                  ('name', '=', 'step_fleet_vehicle_action')])
        alias.res_id = self.env.ref('step_agriculture_core.action_step_fundo').id
        with self.assertRaises(UserError):
            adopt_legacy_records(self.env)
