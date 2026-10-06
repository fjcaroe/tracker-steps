import hmac
import json
from odoo import http
from odoo.http import request
from ..provider import signature_valid, normalize


class Webhook(http.Controller):
    @http.route('/whatsapp/webhook/<string:key>', type='http', auth='public', csrf=False, methods=['GET','POST'], save_session=False)
    def webhook(self, key, **params):
        channel = request.env['step.helpdesk.wa.channel'].sudo().search([
            ('route_key','=',key), ('enabled','=',True), ('provider','=','meta_cloud')], limit=1)
        if not channel:
            return request.make_response('Not found', status=404)
        if request.httprequest.method=='GET':
            if params.get('hub.mode')!='subscribe' or not hmac.compare_digest(params.get('hub.verify_token',''), channel.verify_token or ''):
                return request.make_response('Forbidden',status=403)
            return request.make_response(str(params.get('hub.challenge',''))[:256],status=200)
        if (request.httprequest.content_length or 0)>262144:
            return request.make_response('Too large',status=413)
        raw=request.httprequest.get_data()
        if len(raw)>262144:
            return request.make_response('Too large',status=413)
        if not signature_valid(raw,request.httprequest.headers.get('X-Hub-Signature-256'),channel.app_secret):
            return request.make_response('Forbidden',status=403)
        try:
            payload=json.loads(raw)
            if not isinstance(payload,dict):
                raise ValueError('invalid_payload')
            events=normalize(payload,channel.account_id,channel.phone_number_id)
        except (ValueError,TypeError,AttributeError,KeyError):
            return request.make_response('Invalid event',status=400)
        # The HTTP transaction commits these events before a successful reply.
        # No network or Helpdesk operations occur inside this signed webhook.
        channel._ingest(events)
        return request.make_json_response({'accepted':len(events)},status=200)
