# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import MobilizationCommon


@tagged('post_install', '-at_install')
class TestSecurity(MobilizationCommon):

    def test_plain_user_cannot_cost_trip(self):
        plain_user = self.env['res.users'].create({
            'name': 'Solo lectura', 'login': 'movi_reader@example.com',
            'company_id': self.company.id, 'company_ids': [(4, self.company.id)],
            'groups_id': [(4, self.env.ref('step_mobilization.group_mobilization_user').id)],
        })
        trip = self._make_trip()
        trip.action_open()
        self.env['step.movi.registry.line'].create({
            'movi_id': trip.id, 'employee_id': self.employee_1.id, 'operacion': 'in',
        })
        trip.action_close()
        trip.action_validate()
        with self.assertRaises(UserError):
            trip.with_user(plain_user).action_costeo()

    def test_device_token_authentication(self):
        device = self.env['step.mobilization.driver.device'].create({
            'chofer_id': self.driver.id, 'company_id': self.company.id,
        })
        code = device.action_generate_pairing_code()
        claimed_device, token = self.env['step.mobilization.driver.device']._claim(code, 'device-uuid-1')
        self.assertEqual(claimed_device, device)
        self.assertEqual(device.state, 'active')
        authenticated = self.env['step.mobilization.driver.device']._authenticate('device-uuid-1', token)
        self.assertEqual(authenticated, device)

    def test_token_rejected_after_revoke(self):
        device = self.env['step.mobilization.driver.device'].create({
            'chofer_id': self.driver.id, 'company_id': self.company.id,
        })
        code = device.action_generate_pairing_code()
        _, token = self.env['step.mobilization.driver.device']._claim(code, 'device-uuid-2')
        device.action_revoke()
        with self.assertRaises(Exception):
            self.env['step.mobilization.driver.device']._authenticate('device-uuid-2', token)
