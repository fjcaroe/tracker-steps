# -*- coding: utf-8 -*-
"""API móvil de Movilización, versionada bajo /mobilization/v1.

Diseño deliberado:
- No usa el JSON-RPC envelope de Odoo: son rutas HTTP planas que reciben y
  devuelven JSON, para que un cliente móvil no tenga que hablar el protocolo
  interno de Odoo.
- Autenticación por dispositivo (device_uuid + token corto), nunca por
  usuario/contraseña de Odoo — la API no expone ni acepta credenciales Odoo.
- Todo el acceso a datos usa sudo() DESPUÉS de autenticar el dispositivo y
  siempre queda filtrado por el chofer/compañía del dispositivo autenticado;
  nunca se confía en un company_id/partner_id que venga en el payload del
  cliente para decidir qué datos leer o escribir.
- Payloads de más de 256KB se rechazan (límite de tamaño); listas de eventos
  de más de 500 ítems por lote se rechazan (control básico de rate/carga).
- Los logs de esta API nunca imprimen el token ni el código de emparejamiento
  recibidos, sólo su presencia/ausencia y el resultado.
"""

import json
import logging

from odoo import fields, http
from odoo.exceptions import AccessDenied, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 256 * 1024
MAX_BATCH_ITEMS = 500
API_VERSION = '1.0'


def _json_response(payload, status=200):
    body = json.dumps(payload)
    return request.make_response(
        body, status=status, headers=[('Content-Type', 'application/json')])


def _error(message, status=400):
    return _json_response({'error': message}, status=status)


def _read_body():
    raw = request.httprequest.get_data()
    if len(raw) > MAX_BODY_BYTES:
        raise ValidationError('Payload demasiado grande.')
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise ValidationError('JSON inválido: %s' % exc)


def _authenticate():
    device_uuid = request.httprequest.headers.get('X-Device-UUID')
    token = request.httprequest.headers.get('X-Device-Token')
    if not device_uuid or not token:
        raise AccessDenied('Faltan credenciales de dispositivo.')
    return request.env['step.mobilization.driver.device'].sudo()._authenticate(device_uuid, token)


class MobilizationApiController(http.Controller):

    # ---- Salud -----------------------------------------------------------
    @http.route('/mobilization/v1/health', type='http', auth='public', methods=['GET'], csrf=False)
    def health(self, **kwargs):
        return _json_response({'status': 'ok', 'version': API_VERSION})

    @http.route('/mobilization/v1/health/capabilities', type='http', auth='public', methods=['GET'], csrf=False)
    def capabilities(self, **kwargs):
        return _json_response({
            'version': API_VERSION,
            'methods': ['pin', 'barcode', 'nfc', 'manual'],
            'offline_queue': True,
            'max_batch_items': MAX_BATCH_ITEMS,
            'max_body_bytes': MAX_BODY_BYTES,
        })

    # ---- Autenticación -----------------------------------------------------
    @http.route('/mobilization/v1/auth/claim', type='http', auth='public', methods=['POST'], csrf=False)
    def auth_claim(self, **kwargs):
        try:
            body = _read_body()
            code = body.get('pairing_code')
            device_uuid = body.get('device_uuid')
            if not code or not device_uuid:
                return _error('pairing_code y device_uuid son requeridos.')
            device, token = request.env['step.mobilization.driver.device']._claim(code, device_uuid)
            return _json_response({
                'device_uuid': device.device_uuid,
                'token': token,
                'expires_at': device.token_expires_at.isoformat(),
                'chofer_name': device.chofer_id.name,
            })
        except AccessDenied as exc:
            _logger.info('mobilization auth_claim denied: %s', exc)
            return _error(str(exc), status=401)
        except ValidationError as exc:
            return _error(str(exc), status=400)

    @http.route('/mobilization/v1/auth/refresh', type='http', auth='public', methods=['POST'], csrf=False)
    def auth_refresh(self, **kwargs):
        try:
            body = _read_body()
            device_uuid = body.get('device_uuid')
            token = body.get('token')
            if not device_uuid or not token:
                return _error('device_uuid y token son requeridos.')
            device, new_token = request.env['step.mobilization.driver.device']._refresh(device_uuid, token)
            return _json_response({'token': new_token, 'expires_at': device.token_expires_at.isoformat()})
        except AccessDenied as exc:
            return _error(str(exc), status=401)
        except ValidationError as exc:
            return _error(str(exc), status=400)

    # ---- Catálogo -----------------------------------------------------------
    @http.route('/mobilization/v1/catalog', type='http', auth='public', methods=['GET'], csrf=False)
    def catalog(self, **kwargs):
        try:
            device = _authenticate()
        except AccessDenied as exc:
            return _error(str(exc), status=401)
        env = request.env(su=True)
        vehicles = env['fleet.vehicle'].search([('step_mobilization_enabled', '=', True)])
        routes = env['hr.route'].search([('company_id', '=', device.company_id.id)])
        return _json_response({
            'vehicles': [{'id': v.id, 'name': v.display_name, 'max_pass': v.step_max_pass} for v in vehicles],
            'routes': [{'id': r.id, 'name': r.name, 'travel_type': r.travel_type} for r in routes],
        })

    # ---- Sesión de viaje --------------------------------------------------
    @http.route('/mobilization/v1/trips/open', type='http', auth='public', methods=['POST'], csrf=False)
    def trip_open(self, **kwargs):
        try:
            device = _authenticate()
            body = _read_body()
            required = ('recorrido_id', 'vehicle_id', 'direction', 'uuid')
            if not all(body.get(k) for k in required):
                return _error('recorrido_id, vehicle_id, direction y uuid son requeridos.')
            env = request.env(su=True)
            Trip = env['step.movi.registry']
            existing = Trip.search([('uuid', '=', body['uuid'])], limit=1)
            if existing:
                if existing.chofer_id != device.chofer_id:
                    return _error('UUID de viaje ya usado por otro chofer.', status=409)
                return _json_response(self._trip_payload(existing))
            trip = Trip.create({
                'company_id': device.company_id.id,
                'uuid': body['uuid'],
                'recorrido_id': int(body['recorrido_id']),
                'vehicle_id': int(body['vehicle_id']),
                'direction': body['direction'],
                'chofer_id': device.chofer_id.id,
                'partner_id': device.chofer_id.transpor_id.id or device.chofer_id.id,
                'origin': 'mobile',
            })
            trip.action_open()
            return _json_response(self._trip_payload(trip))
        except AccessDenied as exc:
            return _error(str(exc), status=401)
        except (UserError, ValidationError) as exc:
            return _error(str(exc), status=422)

    @http.route('/mobilization/v1/trips/<int:trip_id>/close', type='http', auth='public', methods=['POST'],
                csrf=False)
    def trip_close(self, trip_id, **kwargs):
        try:
            device = _authenticate()
            trip = self._get_own_trip(device, trip_id)
            body = _read_body()
            if body.get('reason'):
                trip.cancel_reason = body['reason']
            trip.action_close()
            return _json_response(self._trip_payload(trip))
        except AccessDenied as exc:
            return _error(str(exc), status=401)
        except (UserError, ValidationError) as exc:
            return _error(str(exc), status=422)

    @http.route('/mobilization/v1/trips/<int:trip_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def trip_status(self, trip_id, **kwargs):
        try:
            device = _authenticate()
            trip = self._get_own_trip(device, trip_id)
            return _json_response(self._trip_payload(trip))
        except AccessDenied as exc:
            return _error(str(exc), status=401)

    # ---- Eventos de pasajero (lote) ---------------------------------------
    @http.route('/mobilization/v1/trips/<int:trip_id>/events', type='http', auth='public', methods=['POST'],
                csrf=False)
    def trip_events(self, trip_id, **kwargs):
        try:
            device = _authenticate()
            trip = self._get_own_trip(device, trip_id)
            body = _read_body()
            items = body.get('events') or []
            if len(items) > MAX_BATCH_ITEMS:
                return _error('Demasiados eventos en un solo lote.', status=413)
            Event = request.env(su=True)['step.mobilization.passenger.event']
            results = []
            for item in items:
                results.append(self._apply_event(Event, trip, device, item))
            return _json_response({'results': results, 'trip': self._trip_payload(trip)})
        except AccessDenied as exc:
            return _error(str(exc), status=401)
        except ValidationError as exc:
            return _error(str(exc), status=400)

    def _apply_event(self, Event, trip, device, item):
        idempotency_key = item.get('idempotency_key')
        if not idempotency_key:
            return {'idempotency_key': None, 'status': 'error', 'error': 'idempotency_key requerido'}
        existing = Event.search([
            ('trip_id', '=', trip.id), ('device_id', '=', device.id),
            ('idempotency_key', '=', idempotency_key)], limit=1)
        if existing:
            return {'idempotency_key': idempotency_key, 'status': 'duplicate', 'event_id': existing.id}
        try:
            event = Event.create({
                'trip_id': trip.id,
                'passenger_id': int(item['passenger_id']),
                'event_type': item['event_type'],
                'device_datetime': item['device_datetime'],
                'server_datetime': fields.Datetime.now(),
                'latitude': item.get('latitude') or 0.0,
                'longitude': item.get('longitude') or 0.0,
                'accuracy': item.get('accuracy') or 0.0,
                'location_source': item.get('location_source') or 'unknown',
                'method': item['method'],
                'device_id': device.id,
                'device_uuid': device.device_uuid,
                'idempotency_key': idempotency_key,
            })
            return {'idempotency_key': idempotency_key, 'status': 'created', 'event_id': event.id}
        except Exception as exc:  # noqa: broad on purpose, one bad item must not fail the whole batch
            _logger.warning('mobilization event rejected trip=%s key=%s: %s', trip.id, idempotency_key, exc)
            return {'idempotency_key': idempotency_key, 'status': 'error', 'error': str(exc)}

    # ---- Puntos GPS (lote) --------------------------------------------------
    @http.route('/mobilization/v1/trips/<int:trip_id>/gps', type='http', auth='public', methods=['POST'],
                csrf=False)
    def trip_gps(self, trip_id, **kwargs):
        try:
            device = _authenticate()
            trip = self._get_own_trip(device, trip_id)
            if trip.state != 'open':
                return _error('El viaje no está abierto; no se aceptan puntos GPS.', status=422)
            body = _read_body()
            items = body.get('points') or []
            if len(items) > MAX_BATCH_ITEMS:
                return _error('Demasiados puntos en un solo lote.', status=413)
            Point = request.env(su=True)['step.mobilization.gps.point']
            results = []
            for item in items:
                key = item.get('idempotency_key')
                if not key:
                    results.append({'status': 'error', 'error': 'idempotency_key requerido'})
                    continue
                existing = Point.search([
                    ('trip_id', '=', trip.id), ('device_id', '=', device.id),
                    ('idempotency_key', '=', key)], limit=1)
                if existing:
                    results.append({'idempotency_key': key, 'status': 'duplicate'})
                    continue
                Point.create({
                    'trip_id': trip.id,
                    'device_id': device.id,
                    'device_datetime': item['device_datetime'],
                    'latitude': item['latitude'],
                    'longitude': item['longitude'],
                    'accuracy': item.get('accuracy') or 0.0,
                    'speed': item.get('speed') or 0.0,
                    'idempotency_key': key,
                })
                results.append({'idempotency_key': key, 'status': 'created'})
            return _json_response({'results': results})
        except AccessDenied as exc:
            return _error(str(exc), status=401)
        except ValidationError as exc:
            return _error(str(exc), status=400)

    # ---- Helpers ------------------------------------------------------------
    @staticmethod
    def _get_own_trip(device, trip_id):
        trip = request.env(su=True)['step.movi.registry'].browse(trip_id)
        if not trip.exists() or trip.chofer_id != device.chofer_id:
            raise AccessDenied('Viaje no encontrado para este chofer.')
        return trip

    @staticmethod
    def _trip_payload(trip):
        return {
            'id': trip.id,
            'uuid': trip.uuid,
            'name': trip.name,
            'state': trip.state,
            'aboard_count': trip.aboard_count,
            'capacity': trip.capacity,
            'overcapacity': trip.overcapacity,
        }
