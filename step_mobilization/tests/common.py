# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase


class MobilizationCommon(TransactionCase):
    """Fixture builder shared by the domain tests (Fase 8.2)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company = Company.create({'name': 'Steps Test Co'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company.id
        cls.env.user.groups_id = [(4, cls.env.ref('step_mobilization.group_mobilization_manager').id)]

        cls.journal = cls.env['account.journal'].create({
            'name': 'Movilización', 'type': 'general', 'code': 'MVJ', 'company_id': cls.company.id,
        })
        account = cls.env['account.account'].search([('company_ids', '=', cls.company.id)], limit=1)
        if not account:
            account = cls.env['account.account'].create({
                'name': 'Gasto Movilización', 'code': 'MVACC',
                'account_type': 'expense', 'company_ids': [(6, 0, [cls.company.id])],
            })
        cls.journal.default_account_id = account.id
        control_account = cls.env['account.account'].create({
            'name': 'Cuenta Control Movilización', 'code': 'MVCTL',
            'account_type': 'liability_current', 'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.journal.account_control_ids = [(6, 0, [control_account.id])]
        cls.company.step_movi_journal_id = cls.journal.id

        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Test Brand'})
        model = cls.env['fleet.vehicle.model'].create({'name': 'Test Model', 'brand_id': brand.id})
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': model.id, 'company_id': cls.company.id,
            'step_max_pass': 2, 'step_min_pass': 1, 'step_mobilization_enabled': True,
        })

        cls.transporter = cls.env['res.partner'].create({
            'name': 'Transportista SPA', 'company_type': 'company', 'step_trans_person': True,
        })
        cls.driver = cls.env['res.partner'].create({
            'name': 'Chofer Test', 'step_chofer': True, 'transpor_id': cls.transporter.id,
        })

        cls.route = cls.env['hr.route'].create({
            'name': 'Ruta Test', 'company_id': cls.company.id, 'desde': 'Fundo', 'hasta': 'Planta',
        })

        product = cls.env['product.template'].create({'name': 'Servicio Movilización', 'is_movi': True})
        cls.pricelist = cls.env['product.pricelist'].create({
            'name': 'Tarifa Test', 'company_id': cls.company.id, 'moviliza': True,
            'transporte_id': cls.transporter.id,
        })
        cls.route.product_id = product.id
        cls.tariff_line = cls.env['product.pricelist.move.line'].create({
            'pricelist_id': cls.pricelist.id, 'recorrido_id': cls.route.id,
            'charge_type': 'fixed', 'tarifa': 1000.0,
        })

        cls.employee_1 = cls.env['hr.employee'].create({'name': 'Trabajador Uno', 'company_id': cls.company.id})
        cls.employee_2 = cls.env['hr.employee'].create({'name': 'Trabajador Dos', 'company_id': cls.company.id})

        cls.device = cls.env['step.mobilization.driver.device'].create({
            'chofer_id': cls.driver.id, 'company_id': cls.company.id,
            'device_uuid': 'test-device', 'state': 'active',
        })

    def _make_trip(self, **overrides):
        vals = {
            'company_id': self.company.id,
            'recorrido_id': self.route.id,
            'vehicle_id': self.vehicle.id,
            'partner_id': self.transporter.id,
            'chofer_id': self.driver.id,
            'pricelist_id': self.pricelist.id,
            'direction': 'ida',
        }
        vals.update(overrides)
        return self.env['step.movi.registry'].create(vals)
