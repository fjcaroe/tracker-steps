"""Same-origin BFF. No Tracker or receiver credentials ever reach the browser."""
import json
import requests
from odoo import http
from odoo.http import request
from werkzeug.exceptions import Forbidden, BadRequest, ServiceUnavailable
from ..signing import sign_identity


def role():
    user = request.env.user
    if user.has_group('base.group_system') or user.has_group('step_tracker_portal.group_tracker_manager'):
        return 'manager'
    if user.has_group('step_tracker_portal.group_tracker_operator'):
        return 'operator'
    if user.has_group('step_tracker_portal.group_tracker_viewer'):
        return 'viewer'
    raise Forbidden('Solicita acceso a Tracker al administrador de tu compañía.')


def company():
    # Odoo browser company cookie is a selector, never authority: verify membership.
    raw = request.httprequest.cookies.get('cids', '').split('-')[0].split(',')[0]
    try:
        selected = int(raw) if raw else request.env.user.company_id.id
    except ValueError:
        raise BadRequest('Compañía inválida')
    if selected not in request.env.user.company_ids.ids:
        raise Forbidden('Compañía no autorizada')
    return request.env['res.company'].browse(selected)


def signed_token(current_role):
    key = request.env['ir.config_parameter'].sudo().get_param('step_tracker_portal.bridge_key')
    if not key:
        raise ServiceUnavailable('Tracker pendiente de configurar')
    return sign_identity(request.db, company().id, request.env.uid, current_role, key)


def call_api(path, method='GET', body=None, params=None):
    # Fixed loopback destination and path allowlist prevent SSRF and legacy API access.
    allowed = ('fleet/snapshot', 'assets', 'assets/', 'view-preferences/', 'security/policies', 'security/incidents', 'security/commands', 'configuration', 'configuration/', 'zones', 'zones/')
    if not any(path == p or (p.endswith('/') and path.startswith(p)) or (p.startswith('security/') and path.startswith(p+'/')) for p in allowed):
        raise Forbidden('Ruta no disponible')
    if '..' in path or '?' in path or '#' in path:
        raise BadRequest('Ruta inválida')
    try:
        return requests.request(method, 'http://127.0.0.1:8000/v1/'+path,
            headers={'Authorization': 'Bearer '+signed_token(role())}, json=body, params=params, timeout=20)
    except requests.RequestException:
        raise ServiceUnavailable('La API Tracker no está disponible; vuelve a intentar')


class TrackerPortal(http.Controller):
    @http.route('/steps_tracker/context', type='http', auth='user', methods=['GET'])
    def context(self):
        current_role = role()
        current_company = company()
        return request.make_json_response({'user_id': request.env.uid, 'user': request.env.user.name,
            'company_id': current_company.id, 'company': current_company.name,
            'tenant_key': '%s:%s' % (request.db, current_company.id), 'role': current_role,
            'csrf_token': request.csrf_token()}, headers={'Cache-Control': 'no-store'})

    @http.route('/steps_tracker/api/<path:path>', type='http', auth='user', methods=['GET', 'POST'], csrf=True)
    def proxy(self, path, **kwargs):
        if request.httprequest.method == 'GET':
            result = call_api(path, params=request.httprequest.args)
        else:
            method = kwargs.get('method', '')
            if method not in ('POST', 'PUT', 'PATCH'):
                raise BadRequest('Método inválido')
            try:
                body = json.loads(kwargs.get('payload', '{}'))
            except ValueError:
                raise BadRequest('JSON inválido')
            result = call_api(path, method, body=body)
        return request.make_response(result.content, status=result.status_code,
            headers=[('Content-Type', 'application/json'), ('Cache-Control', 'no-store')])

    @http.route('/steps_tracker/classic-session', type='http', auth='user', methods=['POST'], csrf=True)
    def classic_session(self, **kwargs):
        """Cambia la sesión Odoo ya validada por un token de la operación clásica (sin segundo login)."""
        current_role = role()
        if current_role == 'viewer':
            raise Forbidden('Tu perfil no incluye la operación clásica.')
        try:
            result = requests.post('http://127.0.0.1:8000/v1/classic-session',
                headers={'Authorization': 'Bearer '+signed_token(current_role)},
                json={'login': request.env.user.login or '', 'name': request.env.user.name or ''}, timeout=20)
        except requests.RequestException:
            raise ServiceUnavailable('La API Tracker no está disponible; vuelve a intentar')
        return request.make_response(result.content, status=result.status_code,
            headers=[('Content-Type', 'application/json'), ('Cache-Control', 'no-store')])

    @http.route('/steps_tracker/import-fleet',type='http', auth='user', methods=['POST'], csrf=True)
    def import_fleet(self, **kwargs):
        if role() != 'manager':
            raise Forbidden()
        current_company = company()
        # Keep record rules and explicitly restrict the selected company; no sudo on fleet.
        vehicles = request.env['fleet.vehicle'].with_company(current_company).search([('company_id', '=', current_company.id)])
        count = 0
        for vehicle in vehicles:
            result = call_api('assets', 'PUT', {'source_id': 'odoo:fleet.vehicle:%s' % vehicle.id,
                'name': vehicle.name, 'plate': vehicle.license_plate or None, 'type': 'vehicle',
                'responsible': vehicle.driver_id.name or None,
                'created_at': vehicle.create_date.isoformat()+'Z'})
            if result.status_code >= 400:
                return request.make_response(result.content, status=result.status_code, headers=[('Content-Type', 'application/json')])
            count += 1
        return request.make_json_response({'imported': count})
