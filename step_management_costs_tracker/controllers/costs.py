"""Costos y gastos de un activo de Tracker, servidos por Odoo (mismo origen, sin credenciales en el navegador).

GET /steps_tracker/costs/assets/<asset_id>?from=YYYY-MM-DD&to=YYYY-MM-DD&hourly=session|hourmeter

* El rol de Tracker solo abre la puerta al portal; los importes salen de los permisos EFECTIVOS del usuario
  sobre Gastos, contabilidad y Gestión y Costos (reglas de registro incluidas, sin ``sudo`` sobre finanzas).
* La compañía es la del selector de Odoo verificada contra las compañías permitidas del usuario.
* El activo se resuelve únicamente por la correspondencia explícita de esa compañía; un ID ajeno o
  manipulado responde 404 igual que uno inexistente.
"""
import re
from datetime import timedelta

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.step_tracker_portal.controllers.portal import company, role

ASSET_ID = re.compile(r'^[0-9A-Fa-f-]{8,64}$')
MAX_DAYS = 366


def _json(payload, status=200):
    return request.make_json_response(payload, status=status, headers={'Cache-Control': 'no-store'})


def _detail(message, status):
    return _json({'detail': message}, status)


class TrackerCostsController(http.Controller):

    @http.route('/steps_tracker/costs/assets/<string:asset_id>', type='http', auth='user', methods=['GET'])
    def asset_costs(self, asset_id, **params):
        role()                                   # 403 si el usuario no tiene ningún rol de Tracker
        current_company = company()              # 403 si la compañía no le está permitida
        request.update_context(allowed_company_ids=[current_company.id])
        env = request.env
        if not ASSET_ID.match(asset_id):
            return _detail('Identificador de activo inválido.', 400)
        try:
            date_to = fields.Date.to_date(params.get('to')) if params.get('to') else fields.Date.context_today(env['res.users'])
            date_from = fields.Date.to_date(params.get('from')) if params.get('from') else date_to - timedelta(days=29)
        except (ValueError, TypeError):
            return _detail('Fechas inválidas (use AAAA-MM-DD).', 400)
        if not date_from or not date_to or date_to < date_from:
            return _detail('El período es inválido.', 400)
        if (date_to - date_from).days > MAX_DAYS:
            return _detail('El período no puede superar %s días.' % MAX_DAYS, 400)
        metric = params.get('hourly') if params.get('hourly') in ('session', 'hourmeter') else 'session'

        Link = env['step.tracker.asset.link']
        link = Link._resolve(current_company, asset_id)
        if not link:
            try:
                remote = Link.sudo()._remote_asset(current_company, asset_id)
            except UserError as exc:
                return _detail(exc.args[0], 503)
            if remote is None:
                return _detail('Activo no encontrado.', 404)
            return _json({'linked': False, 'asset_id': asset_id, 'reason': 'unlinked', 'message': (
                'Este activo no está asociado a un vehículo de Odoo (por ejemplo, fue creado en el portal). Un '
                'administrador de Tracker puede vincularlo en Steps Tracker › Vínculos de activos. No se asocia por '
                'nombre ni por patente.')})

        service = env['step.tracker.vehicle.cost']
        access = service._access()
        if not any(access.values()):
            return _detail('Tu usuario no tiene acceso a gastos ni a costos.', 403)
        vehicle = link.vehicle_id.sudo()         # solo identidad (nombre, patente); los importes usan los permisos del usuario
        try:
            result = service.compute(vehicle=vehicle, date_from=date_from, date_to=date_to, hourly_metric=metric,
                                     company=current_company)
        except AccessError:
            return _detail('Tu usuario no tiene acceso a gastos ni a costos.', 403)
        result.update({
            'linked': True, 'asset_id': asset_id,
            'links': {
                'vehicle': '/odoo/action-fleet.fleet_vehicle_action/%s' % vehicle.id,
                'expenses': ('/odoo/action-step_management_costs_tracker.action_server_vehicle_expenses/%s' % vehicle.id
                             if access['expenses'] else None),
            },
        })
        return _json(result)
