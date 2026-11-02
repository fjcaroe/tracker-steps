"""A current Odoo password authorizes one immediate server-side relay intention."""
import json, re, time
import requests
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied, AccessError
from odoo.addons.step_tracker_portal.controllers.portal import company
from odoo.addons.step_tracker_portal.signing import sign_identity


class StarterControl(http.Controller):
    @http.route('/steps_tracker/starter/<string:asset_id>/command', type='http', auth='user', methods=['POST'], csrf=True)
    def command(self, asset_id, password='', payload='{}', **kwargs):
        def error(detail,status):
            return request.make_json_response({'detail':detail},status=status,headers={'Cache-Control':'no-store'})
        if not re.fullmatch(r'[0-9a-f-]{36}',asset_id) or len(payload)>4096 or len(password)>4096:
            return error('Solicitud inválida.',400)
        user=request.env.user;current=company();access=user._tracker_portal_access(current)
        try:user._tracker_check_asset(current,asset_id)
        except AccessError:return error('Activo no encontrado.',404)
        if not access['starter_control'] or access['control_preview']:
            return error('Este perfil es de consulta o prueba; no emite órdenes físicas.',403)
        stamp=time.time()
        if request.session.get('tracker_starter_auth_after',0)>stamp:return error('Espera unos segundos antes de volver a verificar tu contraseña.',429)
        request.session['tracker_starter_auth_after']=stamp+3
        try:
            body=json.loads(payload)
            user._check_credentials({'type':'password','password':password},{'interactive':True})
        except (AccessDenied,ValueError):
            return error('No se pudo verificar tu contraseña.',403)
        key=request.env['ir.config_parameter'].sudo().get_param('step_tracker_portal.bridge_key')
        access['actuator_auth_at']=int(time.time())
        token=sign_identity(request.db,current.id,user.id,access['role'],key,access=access)
        try:
            response=requests.post('http://127.0.0.1:8000/v1/assets/'+asset_id+'/starter-control/commands',
                headers={'Authorization':'Bearer '+token},json=body,timeout=15)
        except requests.RequestException:
            return error('Entrega sin confirmar. Actualiza el estado; no repitas la orden sin revisar el resultado.',503)
        return request.make_response(response.content,status=response.status_code,
            headers=[('Content-Type','application/json'),('Cache-Control','no-store')])
