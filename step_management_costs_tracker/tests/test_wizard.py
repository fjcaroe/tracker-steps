"""Asistente «Costos Tracker»: resultado legible, avisos y permisos."""
from datetime import date
from unittest.mock import patch

import requests

from odoo.tests import tagged

from odoo.addons.step_tracker_usage.tests.common import FakeTracker

from .common import CostCase


@tagged('post_install', '-at_install')
class TestCostWizard(CostCase):

    def _wizard(self, **extra):
        values = {'scope': 'vehicle', 'vehicle_id': self.vehicle.id, 'company_id': self.company.id,
                  'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)}
        values.update(extra)
        return self.env['step.tracker.cost.wizard'].create(values)

    def _values(self, wizard):
        return {line.label: line for line in wizard.line_ids}

    def test_vehicle_wizard_shows_sections_and_states(self):
        self.usage(1)
        posted = self.expense(123450, state='post')
        self.post_expense_move(posted, 123450)
        wizard = self._wizard()
        wizard.action_compute()
        lines = self._values(wizard)
        self.assertEqual(wizard.state, 'result')
        self.assertIn('123', lines['Costo real contabilizado'].value)
        self.assertEqual(lines['Costo por km'].status, 'ok')
        self.assertIn('km', lines['Costo por km'].value)
        self.assertEqual(lines['Costo por hora de sesión'].status, 'ok')
        self.assertIn('no son horas de motor', lines['Horas de sesión'].note)

    def test_incomplete_indicator_says_so_and_shows_partial_reference(self):
        self.usage(2)
        posted = self.expense(123450, state='post')
        self.post_expense_move(posted, 123450)
        self.expense(10000, state='approve')
        wizard = self._wizard()
        wizard.action_compute()
        km = self._values(wizard)['Costo por km']
        self.assertEqual(km.status, 'incomplete')
        self.assertIn('No disponible / información incompleta', km.value)
        self.assertIn('valor parcial de referencia', km.value)

    def test_center_wizard_and_budget_lines(self):
        center = self.env['step.management.cost.center'].create({
            'name': 'Centro wizard', 'code': 'CW1', 'company_id': self.company.id, 'analytic_account_id': self.analytic_1.id})
        wizard = self.env['step.tracker.cost.wizard'].create({
            'scope': 'center', 'center_id': center.id, 'company_id': self.company.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 15)})
        wizard.action_compute()
        lines = self._values(wizard)
        self.assertEqual(lines['Presupuesto del período'].status, 'unavailable')
        self.assertIn('meses completos', lines['Presupuesto del período'].note)

    def test_open_actions_from_vehicle_and_center(self):
        action = self.vehicle.action_open_tracker_costs()
        wizard = self.env['step.tracker.cost.wizard'].browse(action['res_id'])
        self.assertEqual((wizard.scope, wizard.vehicle_id), ('vehicle', self.vehicle))
        center = self.env['step.management.cost.center'].create({'name': 'C', 'code': 'CW2', 'company_id': self.company.id})
        action = center.action_open_tracker_costs()
        self.assertEqual(self.env['step.tracker.cost.wizard'].browse(action['res_id']).scope, 'center')

    def test_tracker_down_still_computes_with_loaded_data_and_says_so(self):
        self.usage(3)
        wizard = self._wizard(refresh_tracker=True)
        self.company.step_tracker_base_url = 'http://tracker.test'
        with patch.object(type(self.env['step.tracker.sync']), '_get_token', return_value='tok'), \
                FakeTracker(fail=requests.ConnectTimeout('timeout')).patch():
            wizard.action_compute()
        self.assertEqual(wizard.state, 'result')
        self.assertIn('Se calculó con los datos ya cargados', wizard.message)
        self.assertIn('No se modificó ningún documento', wizard.message)

    def test_user_without_finance_access_sees_no_amounts(self):
        posted = self.expense(99999, state='post')
        self.post_expense_move(posted, 99999)
        user = self.env['res.users'].create({
            'name': 'Sin finanzas', 'login': 'trk_wiz_nofin', 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('step_expense_tracker.group_expense_vehicle').id])]})
        wizard = self.env['step.tracker.cost.wizard'].with_user(user).create({
            'scope': 'vehicle', 'vehicle_id': self.vehicle.id, 'company_id': self.company.id,
            'date_from': date(2026, 9, 1), 'date_to': date(2026, 9, 30)})
        wizard.action_compute()
        text = ' '.join(line.value or '' for line in wizard.line_ids)
        self.assertIn('Sin acceso', text)
        self.assertNotIn('99', text.replace('99.', ''))

    def test_forms_expose_costs_and_map_buttons(self):
        fleet_form = self.env['fleet.vehicle'].get_view(view_type='form')['arch']
        self.assertIn('action_open_tracker_costs', fleet_form)
        self.assertIn('action_open_tracker_map', fleet_form)
        self.assertIn('action_open_tracker_costs', self.env['step.management.cost.center'].get_view(view_type='form')['arch'])
        self.assertIn('management_center_id', self.env['step.tracker.cost_center'].get_view(view_type='form')['arch'])
        with self.assertRaisesRegex(Exception, 'no está vinculado'):
            self.vehicle.action_open_tracker_map()
