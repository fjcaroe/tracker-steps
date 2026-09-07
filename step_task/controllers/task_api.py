# -*- coding: utf-8 -*-
"""API same-origin para la PWA Steps Task (``/task/``).

Réplica del patrón de ``step_cosecha/controllers/harvest_api.py`` pero sobre
``step.tarja`` (cabecera de OT de labores) y ``step.tarja.registry`` (líneas de
detalle por trabajador).

Rutas:
    GET  /api/task/health              (público)
    GET  /api/task/session             (público)
    GET  /api/task/ref/<resource>      (usuario)
    GET  /api/task/bootstrap           (usuario)
    GET  /api/task/recent              (usuario)
    POST /api/task/sync                (usuario, mismo origen)
"""

from datetime import datetime, timezone
from urllib.parse import urlsplit

from odoo import fields, http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request


API_VERSION = 1
MAX_BATCH_RECORDS = 100
NO_STORE = [('Cache-Control', 'no-store')]

MOBILE_STATUS_LABEL = {
    'progress': 'En proceso',
    'closed': 'Cerrada',
    'reviewed': 'Revisada',
    'sent': 'Transmitida',
}


class StepTaskApi(http.Controller):
    """Lecturas con las reglas de acceso del usuario; escrituras con sesión
    Odoo y origen del mismo host."""

    # ------------------------------------------------------------------ utils
    def _json(self, payload, status=200):
        return request.make_json_response(payload, status=status, headers=NO_STORE)

    def _server_time(self):
        return fields.Datetime.now().replace(microsecond=0).isoformat() + 'Z'

    def _payload(self):
        payload = request.httprequest.get_json(silent=True)
        return payload if isinstance(payload, dict) else {}

    def _same_origin(self):
        origin = request.httprequest.headers.get('Origin')
        if not origin:
            return True
        expected = urlsplit(request.httprequest.host_url)
        supplied = urlsplit(origin)
        return supplied.scheme in ('http', 'https') and supplied.netloc == expected.netloc

    def _event_datetime(self, value):
        if not value:
            return fields.Datetime.now()
        try:
            parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            if parsed.tzinfo:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return fields.Datetime.to_string(parsed)
        except (TypeError, ValueError):
            raise ValidationError(_('La fecha del registro no tiene un formato válido.'))

    def _item(self, record, **extra):
        return {'id': record.id, 'name': record.display_name, **extra}

    def _m2o_name(self, record, field_name, fallback=''):
        value = record[field_name]
        return value.display_name if value else fallback

    # --------------------------------------------------------------- serializers
    def _order(self, record):
        crew = record.salary_id or record.salary_id_contrac
        date_value = fields.Datetime.context_timestamp(request.env.user, record.hora_inicio) \
            if record.hora_inicio else None
        day = record.date
        return {
            'id': record.mobile_work_order or record.folio or record.name,
            'odoo_id': record.id,
            'date': day.strftime('%d-%m-%Y') if day else '',
            'op_number': record.op_number or '',
            'taskType': dict(record._fields['tarja_type'].selection).get(record.tarja_type, ''),
            'crew': crew.display_name if crew else '',
            'farm': self._m2o_name(record, 'fundo_id'),
            'species': self._m2o_name(record, 'especie_id'),
            'authorizer': self._m2o_name(record, 'auto_id'),
            'contractor': self._m2o_name(record, 'partner_id', _('Propio')),
            'device': record.mobile_device or '',
            'mobileUser': record.mobile_user or '',
            'workers': record.num_workers,
            'startTime': date_value.strftime('%H:%M') if date_value else '',
            'sendType': dict(record._fields['send_type'].selection).get(record.send_type, ''),
            'status': MOBILE_STATUS_LABEL.get(record.mobile_status or 'progress', 'En proceso'),
            'statusKey': record.mobile_status or 'progress',
            'hrOrdinarias': record.hr_ordinarias,
            'hrExtras': record.hr_extras,
        }

    def _reference_data(self, resource, query='', limit=200):
        company = request.env.company
        query = (query or '').strip()
        limit = max(1, min(int(limit or 200), 5000))
        specs = {
            'workers': ('hr.employee', [('company_id', 'in', [False, company.id])]),
            'crews': ('hr.salary.custom', [('company_id', '=', company.id)]),
            'farms': ('step.fundo', [('company_id', '=', company.id)]),
            'species': ('step.especie', [('company_id', 'in', [False, company.id])]),
            'varieties': ('step.variedad', [('company_id', 'in', [False, company.id])]),
            'cost_centers': ('account.analytic.account', [('company_id', 'in', [False, company.id])]),
            'labors': ('product.template', [('is_labor', '=', True)]),
            'contractors': ('res.partner', [('is_company', '=', True)]),
        }
        if resource not in specs:
            raise UserError(_('Maestro no soportado: %s', resource))
        model_name, domain = specs[resource]
        if query:
            domain = domain + [('name', 'ilike', query)]
        records = request.env[model_name].search(domain, order='name, id', limit=limit)

        if resource == 'workers':
            return [self._item(
                record,
                nip=record.pin or '',
                sex=(record.gender or '')[:1].upper(),
                contractor_id=record.contratista_id.id if record.contratista_id else False,
            ) for record in records]
        if resource == 'crews':
            return [self._item(
                record,
                type=record.group_type or '',
                farm_id=record.fundo_id.id if record.fundo_id else False,
                worker_ids=record.salary_line.employee_id.ids,
            ) for record in records]
        if resource == 'varieties':
            return [self._item(
                record,
                species=record.especie_id.display_name if record.especie_id else '',
            ) for record in records]
        if resource == 'cost_centers':
            return [self._item(
                record,
                farm_id=record.fundo_id.id if 'fundo_id' in record._fields and record.fundo_id else False,
                variety_id=record.variedad_id.id if 'variedad_id' in record._fields and record.variedad_id else False,
            ) for record in records]
        if resource == 'labors':
            return [self._item(
                record,
                uom=record.uom_id.display_name if record.uom_id else '',
                relacion_trato=record.uom_trato.display_name if record.uom_trato else '',
                relacion_trato_id=record.uom_trato.id if record.uom_trato else False,
            ) for record in records]
        return [self._item(record) for record in records]

    # --------------------------------------------------------------- write path
    def _find_exact(self, model_name, name, domain=None):
        if not name:
            return request.env[model_name]
        return request.env[model_name].search(
            (domain or []) + [('name', '=ilike', str(name).strip())], limit=1)

    def _get_or_create_order(self, data):
        order_data = data.get('work_order') if isinstance(data.get('work_order'), dict) else {}
        reference = str(order_data.get('id') or data.get('work_order_id') or '').strip()
        if not reference:
            raise ValidationError(_('El registro no indica una orden de trabajo.'))

        model = request.env['step.tarja']
        order = model.search([
            ('company_id', '=', request.env.company.id),
            '|', ('mobile_work_order', '=', reference), ('mobile_uid', '=', reference),
        ], limit=1)
        if order:
            return order

        own = (order_data.get('contractor') or '').strip().lower() in ('', 'propio')
        company = request.env.company
        farm = self._find_exact('step.fundo', order_data.get('farm'), [('company_id', '=', company.id)])
        crew_name = str(order_data.get('crew') or '').split(' · ', 1)[0]
        crew = self._find_exact('hr.salary.custom', crew_name, [('company_id', '=', company.id)])
        if not crew:
            raise ValidationError(_('No se encontró la cuadrilla "%s".', order_data.get('crew') or ''))
        contractor = request.env['res.partner']
        if not own:
            contractor = self._find_exact('res.partner', order_data.get('contractor'))

        authorizer = self._find_exact('hr.employee', order_data.get('authorizer'))
        started = self._event_datetime(order_data.get('start_datetime')) if order_data.get('start_datetime') else False

        values = {
            'tarja_type': 'propio' if own else 'contratista',
            'date': fields.Date.context_today(model),
            'company_id': company.id,
            'user_id': request.env.user.id,
            'fundo_id': farm.id or False,
            'auto_id': authorizer.id or False,
            'mobile_uid': str(order_data.get('client_uuid') or reference),
            'mobile_work_order': reference,
            'mobile_device': str(order_data.get('device') or '') or False,
            'mobile_user': str(order_data.get('mobile_user') or request.env.user.display_name),
            'mobile_status': 'progress',
            'op_number': str(order_data.get('op_number') or '') or model._step_task_week_op(),
            'hora_inicio': started,
        }
        if own:
            values['salary_id'] = crew.id
        else:
            values['salary_id_contrac'] = crew.id
            values['partner_id'] = contractor.id or False
        # ``step.tarja.create`` fuerza folio/name por secuencia según tarja_type;
        # la app se referencia siempre por ``mobile_work_order``.
        return model.create(values)

    def _sync_record(self, data):
        client_uuid = str(data.get('client_uuid') or data.get('id') or '').strip()
        if not client_uuid:
            raise ValidationError(_('Cada registro debe incluir client_uuid.'))

        line_model = request.env['step.tarja.registry']
        existing = line_model.search([('mobile_uid', '=', client_uuid)], limit=1)
        if existing:
            return {'client_uuid': client_uuid, 'ok': True, 'duplicate': True, 'id': existing.id}

        worker = request.env['hr.employee']
        worker_id = data.get('worker_id')
        if str(worker_id or '').isdigit():
            worker = worker.browse(int(worker_id)).exists()
        if not worker and data.get('nip'):
            worker = request.env['hr.employee'].search([('pin', '=', str(data['nip']))], limit=1)
        if not worker:
            raise ValidationError(_('No se encontró el trabajador del registro.'))

        labor = request.env['product.template']
        if str(data.get('labor_id') or '').isdigit():
            labor = labor.browse(int(data['labor_id'])).exists()
        elif data.get('labor'):
            labor = self._find_exact('product.template', data.get('labor'), [('is_labor', '=', True)])

        cost = request.env['account.analytic.account']
        if str(data.get('cost_center_id') or '').isdigit():
            cost = cost.browse(int(data['cost_center_id'])).exists()
        elif data.get('cost_center'):
            cost = self._find_exact('account.analytic.account', data.get('cost_center'))

        order = self._get_or_create_order(data)
        contract = request.env['hr.contract'].search(
            [('employee_id', '=', worker.id), ('state', '=', 'open')], limit=1)
        if not contract:
            contract = request.env['hr.contract'].search([('employee_id', '=', worker.id)], limit=1)

        read_method = str(data.get('read_method') or 'manual')
        if read_method not in ('manual', 'barcode', 'qr', 'nfc'):
            read_method = 'manual'

        line = line_model.create({
            'tarja_id': order.id,
            'employee_id': worker.id,
            'contract_id': contract.id or False,
            'cost_id': cost.id or False,
            'labor_id': labor.id or False,
            'uom_id': (labor.uom_id.id if labor and labor.uom_id else False),
            'relacion_trato': (labor.uom_trato.id if labor and labor.uom_trato else False),
            'quantity': float(data.get('quantity') or 0),
            'hrs': float(data.get('hrs_ordinarias') or 0),
            'hrs_extra': float(data.get('hrs_extras') or 0),
            'mobile_uid': client_uuid,
            'read_method': read_method,
            'event_datetime': self._event_datetime(data.get('event_datetime')),
        })
        return {
            'client_uuid': client_uuid,
            'ok': True,
            'duplicate': False,
            'id': line.id,
            'work_order_id': order.id,
        }

    # ---------------------------------------------------------------- endpoints
    @http.route('/api/task/health', type='http', auth='public', methods=['GET'], csrf=False, sitemap=False)
    def health(self, **kwargs):
        return self._json({
            'ok': True, 'api_version': API_VERSION,
            'capabilities': ['session', 'bootstrap', 'references', 'batch_sync', 'idempotency'],
            'max_batch_records': MAX_BATCH_RECORDS,
            'server_time': self._server_time(),
        })

    @http.route('/api/task/session', type='http', auth='public', methods=['GET'], csrf=False, sitemap=False)
    def session(self, **kwargs):
        uid = request.session.uid
        user = request.env['res.users'].browse(uid).exists() if uid else request.env['res.users']
        return self._json({
            'ok': True,
            'connected': bool(user),
            'user': {'id': user.id, 'name': user.display_name} if user else None,
            'company': {'id': user.company_id.id, 'name': user.company_id.display_name} if user else None,
            'login_url': '/web/login?redirect=/task/',
            'server_time': self._server_time(),
        })

    @http.route('/api/task/ref/<string:resource>', type='http', auth='user', methods=['GET'], csrf=False, sitemap=False)
    def reference(self, resource, **kwargs):
        try:
            return self._json({'ok': True, 'items': self._reference_data(
                resource, kwargs.get('q'), kwargs.get('limit'))})
        except (AccessError, UserError, ValidationError, ValueError) as exc:
            return self._json({'ok': False, 'error': str(exc)}, status=422)

    @http.route('/api/task/bootstrap', type='http', auth='user', methods=['GET'], csrf=False, sitemap=False)
    def bootstrap(self, **kwargs):
        try:
            orders = request.env['step.tarja'].search([
                ('company_id', '=', request.env.company.id),
            ], order='date desc, id desc', limit=100)
            return self._json({
                'ok': True,
                'api_version': API_VERSION,
                'server_time': self._server_time(),
                'user': {'id': request.env.user.id, 'name': request.env.user.display_name},
                'company': {'id': request.env.company.id, 'name': request.env.company.display_name},
                'workers': self._reference_data('workers'),
                'crews': self._reference_data('crews'),
                'farms': self._reference_data('farms'),
                'species': self._reference_data('species'),
                'varieties': self._reference_data('varieties'),
                'cost_centers': self._reference_data('cost_centers'),
                'labors': self._reference_data('labors'),
                'contractors': self._reference_data('contractors'),
                'orders': [self._order(record) for record in orders],
            })
        except (AccessError, UserError, ValidationError) as exc:
            return self._json({'ok': False, 'error': str(exc)}, status=403)

    @http.route('/api/task/recent', type='http', auth='user', methods=['GET'], csrf=False, sitemap=False)
    def recent(self, **kwargs):
        orders = request.env['step.tarja'].search([
            ('company_id', '=', request.env.company.id),
        ], order='date desc, id desc', limit=min(int(kwargs.get('limit', 50)), 100))
        return self._json({'ok': True, 'items': [self._order(record) for record in orders]})

    @http.route('/api/task/sync', type='http', auth='user', methods=['POST'], csrf=False, sitemap=False)
    def sync(self, **kwargs):
        if not self._same_origin():
            return self._json({'ok': False, 'error': _('Origen no permitido.')}, status=403)
        payload = self._payload()
        records = payload.get('records')
        if not isinstance(records, list) or not records:
            return self._json({'ok': False, 'error': _('Debe enviar una lista records no vacía.')}, status=422)
        if len(records) > MAX_BATCH_RECORDS:
            return self._json(
                {'ok': False, 'error': _('El lote supera el máximo de %s registros.', MAX_BATCH_RECORDS)},
                status=422)
        results = []
        for data in records:
            if not isinstance(data, dict):
                results.append({'ok': False, 'error': _('Registro inválido.')})
                continue
            try:
                with request.env.cr.savepoint():
                    results.append(self._sync_record(data))
            except (AccessError, UserError, ValidationError, ValueError) as exc:
                results.append({
                    'client_uuid': data.get('client_uuid') or data.get('id'),
                    'ok': False, 'error': str(exc),
                })
        return self._json({
            'ok': all(item.get('ok') for item in results),
            'results': results,
            'server_time': self._server_time(),
        }, status=200)
