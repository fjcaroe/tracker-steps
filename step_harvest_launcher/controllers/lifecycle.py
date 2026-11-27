import hmac

from odoo import fields, http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from .scope import ScopedHarvestApi, environment_scope


class LifecycleHarvestApi(ScopedHarvestApi):
    @http.route('/api/harvest/orders/hours', type='http', auth='user', methods=['GET'], sitemap=False)
    def work_hours(self, order_id=None, crew_id=None, day=None, **kwargs):
        error = self._active_company()
        if error is not None:
            return error
        try:
            if order_id:
                order = self._native_record('step.cosecha.registry', order_id)
            else:
                request.env['step.cosecha.registry'].check_access('read')
                crew = self._native_record('hr.salary.custom', crew_id)
                crew._harvest_check_crew()
                order = request.env['step.cosecha.registry'].new({'company_id': request.env.company.id,
                    'type_tarea': crew.group_type,
                    'salary_id_contrac' if crew.group_type == 'contratista' else 'salary_id': crew.id})
            day = fields.Date.to_date(day)
            if not day:
                raise ValidationError(_('Indique el día de la OT.'))
            return self._json({'ok': True, **order._harvest_hours_summary(day)})
        except (AccessError, UserError, ValidationError, ValueError, TypeError) as exc:
            return self._json({'ok': False, 'error': str(exc)}, status=422)

    def _approvers(self):
        candidates = request.env['res.users'].search([
            ('active', '=', True), ('share', '=', False),
            ('company_ids', 'in', request.env.company.ids)], order='name,id')
        allowed = []
        for user in candidates:
            try:
                request.env['step.cosecha.registry'].with_user(user).with_context(
                    allowed_company_ids=request.env.company.ids).check_access('write')
            except AccessError:
                continue
            allowed.append(user)
        return allowed

    def _reference_data(self, resource, query=None, limit=None):
        if resource == 'approvers':
            return [self._item(user) for user in self._approvers()
                    if not query or query.casefold() in user.display_name.casefold()]
        return super()._reference_data(resource, query, limit)

    def _json(self, payload, status=200):
        if request.session.uid and 'orders' in payload and 'crews' in payload:
            payload = dict(payload, approvers=self._reference_data('approvers'), max_order_records=10000)
        return super()._json(payload, status=status)

    def _harvest_order_extra_values(self, values):
        approver_id = values.get('approver_id', request.env.uid)
        if type(approver_id) is not int or approver_id not in [user.id for user in self._approvers()]:
            raise ValidationError(_('Seleccione un aprobador interno con acceso a esta empresa y a Cosecha.'))
        return dict(super()._harvest_order_extra_values(values), mobile_approver_id=approver_id)

    def _send_records(self, order, payload):
        records = payload.get('records', [])
        manifest = payload.get('delivery_uuids')
        if (not isinstance(records, list) or len(records) > 10000 or not isinstance(manifest, list)
                or len(manifest) > 10000 or any(not isinstance(value, str) or not value.strip() for value in manifest)
                or len(set(manifest)) != len(manifest)):
            raise ValidationError(_('El envío total requiere una lista de hasta 10000 entregas y su manifiesto.'))
        identifiers = []
        values = []
        for row in records:
            if not isinstance(row, dict):
                raise ValidationError(_('El envío contiene una entrega inválida.'))
            identifier = row.get('client_uuid') or row.get('id')
            if not isinstance(identifier, str) or not identifier or identifier not in manifest or identifier in identifiers:
                raise ValidationError(_('Cada entrega pendiente debe conservar su UUID único en el manifiesto de esta OT.'))
            supplied = row.get('work_order') or {}
            if not isinstance(supplied, dict) or supplied.get('odoo_id') and str(supplied['odoo_id']) != str(order.id):
                raise ValidationError(_('El envío total no puede contener entregas de otra OT.'))
            identifiers.append(identifier)
            values.append(dict(row, work_order=dict(supplied, odoo_id=order.id)))
        received = request.env['step.cosecha.tarja.registry.line'].search([('mobile_uid', 'in', identifiers)])
        has_new = bool(set(identifiers) - set(received.mapped('mobile_uid')))
        if has_new:
            if (order.mobile_status != 'reviewed' or order.state != 'apro' or not order.mobile_native_approval
                    or order.mobile_approver_id != request.env.user or order.mobile_approved_by_id != request.env.user):
                raise ValidationError(_(
                    'Las entregas pendientes requieren el envío del aprobador sobre una OT aprobada desde Harvest y sin Costeo. '
                    'Solicite al aprobador reabrir y revisar la OT; los pendientes se conservan.'))
            # The same authorized approver confirms the complete original UUID
            # manifest. Native approval is renewed within this one transaction;
            # any rejected delivery or incomplete manifest rolls everything back.
            order.action_in()
            order.with_context(mail_notrack=True)._harvest_write({'mobile_status': 'progress'})
        results = []
        for row in values:
            result = self._sync_record(row)
            if result.get('ok') is not True:
                raise ValidationError(_('Una entrega no pudo confirmarse. El envío completo se conserva pendiente.'))
            results.append(result)
        if has_new:
            order.action_apro()
            order._harvest_write(dict(order._harvest_approval_values(), mobile_status='reviewed'))
        return results

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
                order._lock_harvest_order()
                results = self._send_records(order, payload) if payload.get('action') == 'send' else []
                order._harvest_transition(payload.get('action'), payload.get('delivery_uuids'), payload.get('work_time'))
                return self._json({'ok': True, 'order': self._order(order),
                                   'confirmed_delivery_uuids': payload['delivery_uuids'], 'results': results})
        except (AccessError, UserError, ValidationError, ValueError, TypeError) as exc:
            return self._json({'ok': False, 'error': str(exc)}, status=422)

    def _order(self, record):
        action = request.env.ref('step_cosecha.action_step_cosecha_registry_contra'
                                 if record.type_tarea == 'contratista' else 'step_cosecha.action_step_cosecha_registry')
        writable = record.has_access('write')
        approver = record.mobile_approver_id
        return dict(super()._order(record),
                    order_day=str(fields.Datetime.context_timestamp(record, record.date).date()) if record.date else '',
                    work_start=record.mobile_work_start.isoformat() + 'Z' if record.mobile_work_start else False,
                    work_end=record.mobile_work_end.isoformat() + 'Z' if record.mobile_work_end else False,
                    work_hours=record.mobile_work_hours, work_day=str(record.mobile_work_day or ''),
                    day_hours=record.mobile_day_hours, last_order=record.mobile_last_order,
                    can_transition=record.has_access('write'),
                    approver_id=approver.id or False, approver=approver.display_name or '',
                    approved_by_id=record.mobile_approved_by_id.id or False,
                    approved_at=str(record.mobile_approved_at or ''),
                    can_approve=writable and (not approver or approver == request.env.user)
                        and record.mobile_status in ('closed', 'reviewed'),
                    can_reopen=writable and record.mobile_status in ('closed', 'reviewed'),
                    can_capture=writable and (record.mobile_status or 'progress') == 'progress' and record.state == 'in',
                    erp_state=record.state,
                    state_changed_at=str(record.mobile_state_date or ''),
                    erp_url='/odoo/action-%s/%s' % (action.id, record.id))

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
        if order.mobile_without_tarja and str(data.get('tarja') or '').strip():
            raise ValidationError(_('Esta OT registra cosecha sin folio de tarja.'))
        values = dict(data, work_order=dict(data.get('work_order') or {}, odoo_id=order.id))
        return super()._sync_record(values)

