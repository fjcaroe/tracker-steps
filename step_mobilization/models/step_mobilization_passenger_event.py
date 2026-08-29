# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class StepMobilizationPassengerEvent(models.Model):
    """Marca de subida/bajada, append-only. Un evento nunca se edita ni se
    borra: una corrección crea un evento nuevo y anula el anterior (state
    'void') dejando ambos en el historial. Es la fuente de verdad que llega
    desde la API móvil; step.movi.registry.line se sigue usando para el
    costeo/reportes existentes y se proyecta desde aquí de forma idempotente."""
    _name = 'step.mobilization.passenger.event'
    _description = 'Evento de marcación de pasajero'
    _order = 'device_datetime desc, id desc'

    trip_id = fields.Many2one('step.movi.registry', string='Viaje', required=True,
                               ondelete='cascade', index=True)
    passenger_id = fields.Many2one('hr.employee', string='Pasajero', required=True, index=True)
    event_type = fields.Selection(
        selection=[('boarding', 'Subida'), ('alighting', 'Bajada')],
        string='Tipo', required=True)
    device_datetime = fields.Datetime(string='Fecha/hora dispositivo', required=True)
    server_datetime = fields.Datetime(string='Fecha/hora servidor', required=True,
                                       default=fields.Datetime.now)
    latitude = fields.Float(string='Latitud', digits=(10, 7))
    longitude = fields.Float(string='Longitud', digits=(10, 7))
    accuracy = fields.Float(string='Precisión GPS (m)')
    location_source = fields.Selection(
        selection=[('gps', 'GPS'), ('network', 'Red'), ('manual', 'Manual'), ('unknown', 'Desconocido')],
        string='Origen ubicación', default='unknown')
    method = fields.Selection(
        selection=[('pin', 'PIN'), ('barcode', 'Código de barras/QR'), ('nfc', 'NFC'), ('manual', 'Manual')],
        string='Método de marcación', required=True)
    device_id = fields.Many2one('step.mobilization.driver.device', string='Dispositivo', index=True,
                                 required=True,
                                 help='Requerido: la deduplicación por idempotency_key sólo funciona si '
                                      'está acotada a un dispositivo. NULL rompería el unique constraint '
                                      '(Postgres no considera dos NULL como iguales).')
    device_uuid = fields.Char(string='UUID dispositivo')
    idempotency_key = fields.Char(string='Idempotency key', required=True, index=True)
    sync_state = fields.Selection(
        selection=[('pending', 'Pendiente'), ('synced', 'Sincronizado'), ('conflict', 'Conflicto')],
        string='Estado de sincronización', default='synced', required=True)
    state = fields.Selection(
        selection=[('valid', 'Válido'), ('void', 'Anulado')],
        string='Estado', default='valid', required=True, copy=False)
    void_reason = fields.Text(string='Motivo de anulación')
    replaced_by_id = fields.Many2one('step.mobilization.passenger.event', string='Reemplazado por', copy=False)
    registry_line_id = fields.Many2one('step.movi.registry.line', string='Línea proyectada',
                                        copy=False, readonly=True)

    _sql_constraints = [
        ('idempotency_key_unique', 'unique(trip_id, device_id, idempotency_key)',
         'Este evento ya fue recibido (idempotency key duplicada para el mismo dispositivo/viaje).'),
    ]

    def action_void(self, reason):
        for event in self:
            if event.state == 'void':
                continue
            event.write({'state': 'void', 'void_reason': reason})
            if event.registry_line_id:
                event.registry_line_id.unlink()

    def _project_to_registry_line(self):
        """Proyecta el evento a step.movi.registry.line para no romper el
        costeo/reportes actuales. Idempotente: la constraint unique sobre
        passenger_event_id en la línea impide duplicar si se re-sincroniza."""
        RegistryLine = self.env['step.movi.registry.line']
        for event in self:
            if event.state != 'valid' or event.registry_line_id:
                continue
            if event.trip_id.state not in ('open',):
                raise UserError('El viaje %s no está abierto; no se pueden registrar marcaciones.'
                                 % event.trip_id.name)
            existing = RegistryLine.search([
                ('movi_id', '=', event.trip_id.id),
                ('employee_id', '=', event.passenger_id.id),
                ('operacion', '=', 'in' if event.event_type == 'boarding' else 'out'),
                ('passenger_event_id', '=', False),
            ], limit=1)
            vals = {
                'movi_id': event.trip_id.id,
                'employee_id': event.passenger_id.id,
                'operacion': 'in' if event.event_type == 'boarding' else 'out',
                'passenger_event_id': event.id,
            }
            if event.event_type == 'boarding':
                vals['hr_in'] = event.device_datetime
            else:
                vals['hr_out'] = event.device_datetime
            if existing:
                existing.write(vals)
                line = existing
            else:
                line = RegistryLine.create(vals)
            event.registry_line_id = line.id

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        events._project_to_registry_line()
        return events
