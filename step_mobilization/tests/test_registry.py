# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import MobilizationCommon


@tagged('post_install', '-at_install')
class TestRegistry(MobilizationCommon):

    def test_company_document_type_is_the_native_latam_relation(self):
        field=self.env['res.company']._fields['step_movi_document_type_id']
        self.assertEqual(field.comodel_name,'l10n_latam.document.type')
        document_type=self.env['l10n_latam.document.type'].create({
            'name':'Private mobilization document fixture','code':'991',
            'country_id':self.env.ref('base.cl').id,
        })
        self.company.step_movi_document_type_id=document_type
        self.assertEqual(self.company.step_movi_document_type_id,document_type)

    def test_missing_tariff_raises(self):
        other_route = self.env['hr.route'].create({'name': 'Sin tarifa', 'company_id': self.company.id})
        trip = self._make_trip(recorrido_id=other_route.id)
        trip.action_open()
        self.env['step.movi.registry.line'].create({
            'movi_id': trip.id, 'employee_id': self.employee_1.id, 'operacion': 'in',
        })
        trip.action_close()
        trip.action_validate()
        with self.assertRaises(UserError):
            trip.action_costeo()

    def test_costeo_no_duplicate_on_recompute(self):
        trip = self._make_trip()
        trip.action_open()
        self.env['step.movi.registry.line'].create({
            'movi_id': trip.id, 'employee_id': self.employee_1.id, 'operacion': 'in',
        })
        self.env['step.movi.registry.line'].create({
            'movi_id': trip.id, 'employee_id': self.employee_2.id, 'operacion': 'in',
        })
        trip.action_close()
        trip.action_validate()
        trip.action_costeo()
        self.assertEqual(len(trip.movi_cost_line), 2)
        self.assertAlmostEqual(sum(trip.movi_cost_line.mapped('cost_total')), 1000.0)
        # volver y recostear no debe duplicar líneas
        trip.action_to_costeo()
        trip.action_costeo()
        self.assertEqual(len(trip.movi_cost_line), 2)

    def test_costeo_divides_by_unique_passengers_not_lines(self):
        """Bug detectado en step_hr: dividía por len(movi_line), que cuenta
        entrada+salida por separado. Un solo pasajero con ida y vuelta debe
        seguir contando como 1 pasajero único al prorratear la tarifa fija."""
        trip = self._make_trip(direction='ida_vuelta')
        self.tariff_line.cobro_type  # related to route travel_type
        self.route.travel_type = 'ida_vuelta'
        trip.action_open()
        self.env['step.movi.registry.line'].create({
            'movi_id': trip.id, 'employee_id': self.employee_1.id, 'operacion': 'in',
        })
        self.env['step.movi.registry.line'].create({
            'movi_id': trip.id, 'employee_id': self.employee_1.id, 'operacion': 'out',
        })
        trip.action_close()
        trip.action_validate()
        trip.action_costeo()
        self.assertEqual(len(trip.movi_cost_line), 1)
        self.assertAlmostEqual(trip.movi_cost_line.cost_total, 1000.0)

    def test_overcapacity_flag(self):
        trip = self._make_trip()
        trip.action_open()
        employee_3 = self.env['hr.employee'].create({'name': 'Tres', 'company_id': self.company.id})
        for emp in (self.employee_1, self.employee_2, employee_3):
            self.env['step.mobilization.passenger.event'].create({
                'trip_id': trip.id, 'passenger_id': emp.id, 'event_type': 'boarding',
                'device_datetime': '2026-08-25 10:00:00', 'method': 'pin', 'device_id': self.device.id,
                'idempotency_key': 'evt-%s' % emp.id,
            })
        self.assertTrue(trip.overcapacity)
        self.assertEqual(trip.aboard_count, 3)

    def test_cancel_requires_reason(self):
        trip = self._make_trip()
        with self.assertRaises(ValidationError):
            trip.action_cancel()
        trip.cancel_reason = 'Prueba'
        trip.action_cancel()
        self.assertEqual(trip.state, 'cancelled')

    def test_accounting_is_idempotent(self):
        trip = self._make_trip()
        trip.action_open()
        self.env['step.movi.registry.line'].create({
            'movi_id': trip.id, 'employee_id': self.employee_1.id, 'operacion': 'in',
        })
        trip.action_close()
        trip.action_validate()
        trip.action_costeo()
        trip.action_conta()
        self.assertTrue(trip.invoice_id)
        self.assertEqual(trip.state, 'accounted')
        with self.assertRaises(UserError):
            trip.action_conta()

    def test_unlink_blocked_after_draft(self):
        trip = self._make_trip()
        trip.action_open()
        with self.assertRaises(UserError):
            trip.unlink()
