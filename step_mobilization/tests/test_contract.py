# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import MobilizationCommon


@tagged('post_install', '-at_install')
class TestContract(MobilizationCommon):

    def _make_contract(self):
        template = self.env['step.mobilization.contract.template'].create({
            'name': 'Plantilla test', 'body': '<p>{{company_name}} - {{transporter_name}}</p>',
        })
        contract = self.env['step.mobilization.contract'].create({
            'company_id': self.company.id, 'partner_id': self.transporter.id,
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
            'template_id': template.id, 'route_ids': [(6, 0, [self.route.id])],
        })
        return template, contract

    def test_approve_blocked_without_validated_template(self):
        template, contract = self._make_contract()
        contract.action_submit()
        with self.assertRaises(UserError):
            contract.action_approve()

    def test_rate_snapshot_freezes_on_first_pdf(self):
        template, contract = self._make_contract()
        template.action_validate()
        contract.action_submit()
        contract.action_approve()
        contract._freeze_rate_snapshot()
        self.assertEqual(len(contract.rate_snapshot_ids), 1)
        self.assertEqual(contract.rate_snapshot_ids.amount, 1000.0)
        # cambiar la tarifa vigente no debe alterar la instantánea ya congelada
        self.tariff_line.tarifa = 5000.0
        contract._freeze_rate_snapshot()
        self.assertEqual(len(contract.rate_snapshot_ids), 1)
        self.assertEqual(contract.rate_snapshot_ids.amount, 1000.0)

    def test_render_body_substitutes_variables(self):
        template, contract = self._make_contract()
        rendered = contract.render_body()
        self.assertIn(self.company.name, rendered)
        self.assertIn(self.transporter.name, rendered)
        self.assertNotIn('{{', rendered)
