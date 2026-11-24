import hmac

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from .scope import ScopedHarvestApi, environment_scope


class LifecycleHarvestApi(ScopedHarvestApi):
    @http.route('/api/harvest/orders/transition', type='http', auth='user', methods=['POST'], csrf=False, sitemap=False)
    def transition(self, **kwargs):
        error = self._active_company()
        if error is not None:
            return error
        if not self._same_origin():
            return self._json({'ok': False, 'error': _('Origen no permitido.')}, status=403)
        payload = self._payload()
        supplied = payload.get('scope')
        if not isinstance(supplied, str) or not hmac.compare_digest(supplied, environment_scope(request.env)):
            return self._json({'ok': False, 'error': _(
                'La sesión o la empresa cambió. Actualice Harvest; los pendientes se conservan.')}, status=409)
        try:
            with request.env.cr.savepoint():
                values = payload.get('work_order')
                if isinstance(values, dict) and values.get('local_uuid'):
                    payload['work_order'] = dict(values, client_uuid=values['local_uuid'])
                order = self._get_or_create_order(payload)
                order._harvest_transition(payload.get('action'), payload.get('delivery_uuids'))
                return self._json({'ok': True, 'order': self._order(order),
                                   'confirmed_delivery_uuids': payload['delivery_uuids']})
        except (AccessError, UserError, ValidationError, ValueError) as exc:
            return self._json({'ok': False, 'error': str(exc)}, status=422)

    def _order(self, record):
        return dict(super()._order(record),
                    can_transition=record.has_access('write'),
                    state_changed_at=str(record.mobile_state_date or ''),
                    erp_url='/odoo/step.cosecha.registry/%s' % record.id)

    def _sync_record(self, data):
        identifier = str(data.get('client_uuid') or data.get('id') or '').strip()
        existing = request.env['step.cosecha.tarja.registry.line'].search([
            ('mobile_uid', '=', identifier)], limit=1) if identifier else False
        if existing:
            order = self._native_record('step.cosecha.registry', existing.registry_id.id)
            values = data.get('work_order') if isinstance(data.get('work_order'), dict) else {}
            if values.get('odoo_id') and str(values['odoo_id']) != str(order.id):
                raise ValidationError(_('La entrega ya pertenece a otra OT.'))
            # Return the native relation also on retries, including closed OTs.
            return {'client_uuid': identifier, 'ok': True, 'duplicate': True,
                    'id': existing.id, 'work_order_id': order.id}
        order = self._get_or_create_order(data)
        order._lock_harvest_order()
        if (order.mobile_status or 'progress') != 'progress' or order.state != 'in':
            raise ValidationError(_('La OT está cerrada o aprobada en Odoo y no admite nuevas entregas móviles.'))
        values = dict(data, work_order=dict(data.get('work_order') or {}, odoo_id=order.id))
        return super()._sync_record(values)

