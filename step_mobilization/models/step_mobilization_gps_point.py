# -*- coding: utf-8 -*-

from odoo import fields, models


class StepMobilizationGpsPoint(models.Model):
    """Puntos GPS de un viaje. Sólo se registran mientras el viaje está
    'open' (sesión activa) — la API rechaza puntos fuera de esa ventana, ver
    controllers/mobilization_api.py."""
    _name = 'step.mobilization.gps.point'
    _description = 'Punto GPS de viaje de movilización'
    _order = 'device_datetime'

    trip_id = fields.Many2one('step.movi.registry', string='Viaje', required=True,
                               ondelete='cascade', index=True)
    device_id = fields.Many2one('step.mobilization.driver.device', string='Dispositivo', index=True,
                                 required=True)
    device_datetime = fields.Datetime(string='Fecha/hora dispositivo', required=True)
    server_datetime = fields.Datetime(string='Fecha/hora servidor', required=True, default=fields.Datetime.now)
    latitude = fields.Float(string='Latitud', required=True, digits=(10, 7))
    longitude = fields.Float(string='Longitud', required=True, digits=(10, 7))
    accuracy = fields.Float(string='Precisión (m)')
    speed = fields.Float(string='Velocidad (km/h)')
    idempotency_key = fields.Char(string='Idempotency key', required=True)

    _sql_constraints = [
        ('idempotency_key_unique', 'unique(trip_id, device_id, idempotency_key)',
         'Este punto GPS ya fue recibido.'),
    ]
