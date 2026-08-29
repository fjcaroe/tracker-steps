# -*- coding: utf-8 -*-

from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import MobilizationCommon


@tagged('post_install', '-at_install')
class TestPassengerEvent(MobilizationCommon):

    def test_boarding_projects_to_registry_line(self):
        trip = self._make_trip()
        trip.action_open()
        event = self.env['step.mobilization.passenger.event'].create({
            'trip_id': trip.id, 'passenger_id': self.employee_1.id, 'event_type': 'boarding',
            'device_datetime': '2026-08-25 08:00:00', 'method': 'pin', 'device_id': self.device.id,
            'idempotency_key': 'k1',
        })
        self.assertTrue(event.registry_line_id)
        self.assertEqual(event.registry_line_id.operacion, 'in')
        self.assertEqual(len(trip.movi_line), 1)

    @mute_logger('odoo.sql_db')
    def test_duplicate_idempotency_key_rejected(self):
        trip = self._make_trip()
        trip.action_open()
        self.env['step.mobilization.passenger.event'].create({
            'trip_id': trip.id, 'passenger_id': self.employee_1.id, 'event_type': 'boarding',
            'device_datetime': '2026-08-25 08:00:00', 'method': 'pin', 'device_id': self.device.id,
            'idempotency_key': 'dup',
        })
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env['step.mobilization.passenger.event'].create({
                'trip_id': trip.id, 'passenger_id': self.employee_1.id, 'event_type': 'boarding',
                'device_datetime': '2026-08-25 08:00:05', 'method': 'pin', 'device_id': self.device.id,
                'idempotency_key': 'dup',
            })

    def test_void_removes_projected_line(self):
        trip = self._make_trip()
        trip.action_open()
        event = self.env['step.mobilization.passenger.event'].create({
            'trip_id': trip.id, 'passenger_id': self.employee_1.id, 'event_type': 'boarding',
            'device_datetime': '2026-08-25 08:00:00', 'method': 'pin', 'device_id': self.device.id,
            'idempotency_key': 'k2',
        })
        line = event.registry_line_id
        event.action_void('marcación errónea')
        self.assertEqual(event.state, 'void')
        self.assertFalse(line.exists())
