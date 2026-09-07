# -*- coding: utf-8 -*-

from datetime import datetime, timezone
from urllib.parse import urlsplit

from odoo import fields, http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request


API_VERSION = 1
MAX_BATCH_RECORDS = 100
NO_STORE = [('Cache-Control', 'no-store')]


class StepHarvestApi(http.Controller):
    """API same-origin para la PWA Steps Harvest.

    Las lecturas respetan las reglas de acceso del usuario conectado. Las
    escrituras requieren sesión Odoo y un origen del mismo host.
    """

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
        # Nginx termina TLS y puede presentar ``http`` a Odoo. El host debe
        # coincidir exactamente y el navegador sólo puede declarar HTTP(S).
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
            raise ValidationError(_('La fecha de la entrega no tiene un formato válido.'))

    def _item(self, record, **extra):
        return {'id': record.id, 'name': record.display_name, **extra}

    def _m2o_name(self, record, field_name, fallback=''):
        value = record[field_name]
        return value.display_name if value else fallback

    def _order(self, record):
        status = {
            'progress': 'En proceso', 'closed': 'Cerrada',
            'reviewed': 'Revisada', 'sent': 'Enviada',
        }.get(record.mobile_status or 'progress', 'En proceso')
        crew = record.salary_id or record.salary_id_contrac
        species = record.variedad_id.especie_id.display_name if record.variedad_id else ''
        date_value = fields.Datetime.context_timestamp(request.env.user, record.date) if record.date else None
        return {
            'id': record.mobile_work_order or record.folio or record.name,
            'odoo_id': record.id,
            'date': date_value.strftime('%d %b %Y') if date_value else '',
            'crew': crew.display_name if crew else '',
            'farm': self._m2o_name(record, 'fundo_id'),
            'species': species,
            'variety': self._m2o_name(record, 'variedad_id'),
            'costCenter': self._m2o_name(record, 'cost_id'),
            'harvestType': dict(record._fields['type_cosecha'].selection).get(record.type_cosecha, ''),
            'contractor': self._m2o_name(record, 'partner_id', _('Propio')),
            'status': status,
            'start': date_value.strftime('%H:%M') if date_value else '',
            'boxes': record.total_boxes,
            'kilos': record.total_kilos,
        }

    def _reference_data(self, resource, query='', limit=200):
        company = request.env.company
        query = (query or '').strip()
        limit = max(1, min(int(limit or 200), 500))
        specs = {
            'workers': ('hr.employee', [('company_id', 'in', [False, company.id])]),
            'farms': ('step.fundo', [('company_id', '=', company.id)]),
            'varieties': ('step.variedad', [('company_id', '=', company.id)]),
            'cost_centers': ('account.analytic.account', [('company_id', 'in', [False, company.id])]),
            'operation_locations': ('step.cosecha.ubicacion', [('company_id', '=', company.id)]),
            'crews': ('hr.salary.custom', [('company_id', '=', company.id)]),
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
        if resource == 'varieties':
            return [self._item(record, species=record.especie_id.display_name) for record in records]
        if resource == 'crews':
            return [self._item(
                record,
                type=record.group_type or '',
                farm_id=record.fundo_id.id if record.fundo_id else False,
                worker_ids=record.salary_line.employee_id.ids,
            ) for record in records]
        if resource == 'cost_centers':
            return [self._item(
                record,
                farm_id=record.fundo_id.id if record.fundo_id else False,
                variety_id=record.variedad_id.id if record.variedad_id else False,
            ) for record in records]
        return [self._item(record) for record in records]

    def _find_exact(self, model_name, name, domain=None):
        if not name:
            return request.env[model_name]
        return request.env[model_name].search((domain or []) + [('name', '=ilike', str(name).strip())], limit=1)

    def _get_or_create_order(self, data):
        order_data = data.get('work_order') if isinstance(data.get('work_order'), dict) else {}
        reference = str(order_data.get('id') or data.get('work_order_id') or '').strip()
        if not reference:
            raise ValidationError(_('La entrega no indica una orden de trabajo.'))
        registry_model = request.env['step.cosecha.registry']
        registry = registry_model.search([
            ('company_id', '=', request.env.company.id),
            '|', ('mobile_work_order', '=', reference), ('folio', '=', reference),
        ], limit=1)
        if registry:
            return registry

        own = (order_data.get('contractor') or '').strip().lower() in ('', 'propio')
        farm = self._find_exact('step.fundo', order_data.get('farm'), [('company_id', '=', request.env.company.id)])
        variety = self._find_exact('step.variedad', order_data.get('variety'), [('company_id', '=', request.env.company.id)])
        cost = self._find_exact('account.analytic.account', order_data.get('costCenter'))
        crew_name = str(order_data.get('crew') or '').split(' · ', 1)[0]
        crew = self._find_exact('hr.salary.custom', crew_name, [('company_id', '=', request.env.company.id)])
        contractor = self._find_exact('res.partner', order_data.get('contractor')) if not own else request.env['res.partner']
        unit = request.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not unit:
            unit = request.env['uom.uom'].search([], limit=1)
        if not unit:
            raise ValidationError(_('No existe una unidad de medida para crear la cosecha.'))
        values = {
            'name': reference,
            'folio': reference,
            'mobile_uid': str(order_data.get('client_uuid') or '') or False,
            'mobile_work_order': reference,
            'mobile_status': 'progress',
            'type_tarea': 'propio' if own else 'contratista',
            'product_uom_id': unit.id,
            'date': fields.Datetime.now(),
            'company_id': request.env.company.id,
            'responsable_id': request.env.user.id,
            'fundo_id': farm.id or False,
            'variedad_id': variety.id or False,
            'cost_id': cost.id or False,
            'partner_id': contractor.id or False,
        }
        if crew:
            values['salary_id' if own else 'salary_id_contrac'] = crew.id
        return registry_model.create(values)

    def _sync_record(self, data):
        client_uuid = str(data.get('client_uuid') or data.get('id') or '').strip()
        if not client_uuid:
            raise ValidationError(_('Cada entrega debe incluir client_uuid.'))
        line_model = request.env['step.cosecha.tarja.registry.line']
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
            raise ValidationError(_('No se encontró el trabajador de la entrega.'))
        registry = self._get_or_create_order(data)
        line = line_model.create({
            'registry_id': registry.id,
            'employee_id': worker.id,
            'mobile_uid': client_uuid,
            'mobile_hilera': str(data.get('row') or ''),
            'num_tarja': str(data.get('tarja') or ''),
            'date_tarja': self._event_datetime(data.get('event_datetime')),
            'qty_caja': float(data.get('boxes') or 0),
            'qty_kg': float(data.get('kilos') or 0),
            'quantity': float(data.get('kilos') or data.get('boxes') or 0),
        })
        return {'client_uuid': client_uuid, 'ok': True, 'duplicate': False, 'id': line.id, 'work_order_id': registry.id}

    @http.route('/api/harvest/health', type='http', auth='public', methods=['GET'], csrf=False, sitemap=False)
    def health(self, **kwargs):
        return self._json({
            'ok': True, 'api_version': API_VERSION,
            'capabilities': ['session', 'bootstrap', 'references', 'batch_sync', 'idempotency'],
            'max_batch_records': MAX_BATCH_RECORDS,
            'server_time': self._server_time(),
        })

    @http.route('/api/harvest/session', type='http', auth='public', methods=['GET'], csrf=False, sitemap=False)
    def session(self, **kwargs):
        uid = request.session.uid
        user = request.env['res.users'].browse(uid).exists() if uid else request.env['res.users']
        return self._json({
            'ok': True,
            'connected': bool(user),
            'user': {'id': user.id, 'name': user.display_name} if user else None,
            'company': {'id': user.company_id.id, 'name': user.company_id.display_name} if user else None,
            'login_url': '/web/login?redirect=/cosecha/',
            'server_time': self._server_time(),
        })

    @http.route('/api/harvest/ref/<string:resource>', type='http', auth='user', methods=['GET'], csrf=False, sitemap=False)
    def reference(self, resource, **kwargs):
        try:
            return self._json({'ok': True, 'items': self._reference_data(resource, kwargs.get('q'), kwargs.get('limit'))})
        except (AccessError, UserError, ValidationError, ValueError) as exc:
            return self._json({'ok': False, 'error': str(exc)}, status=422)

    @http.route('/api/harvest/bootstrap', type='http', auth='user', methods=['GET'], csrf=False, sitemap=False)
    def bootstrap(self, **kwargs):
        try:
            orders = request.env['step.cosecha.registry'].search([
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
                'varieties': self._reference_data('varieties'),
                'cost_centers': self._reference_data('cost_centers'),
                'operation_locations': self._reference_data('operation_locations'),
                'orders': [self._order(record) for record in orders],
            })
        except (AccessError, UserError, ValidationError) as exc:
            return self._json({'ok': False, 'error': str(exc)}, status=403)

    @http.route('/api/harvest/cosecha/recent', type='http', auth='user', methods=['GET'], csrf=False, sitemap=False)
    def recent(self, **kwargs):
        orders = request.env['step.cosecha.registry'].search([
            ('company_id', '=', request.env.company.id),
        ], order='date desc, id desc', limit=min(int(kwargs.get('limit', 50)), 100))
        return self._json({'ok': True, 'items': [self._order(record) for record in orders]})

    @http.route('/api/harvest/sync', type='http', auth='user', methods=['POST'], csrf=False, sitemap=False)
    def sync(self, **kwargs):
        if not self._same_origin():
            return self._json({'ok': False, 'error': _('Origen no permitido.')}, status=403)
        payload = self._payload()
        records = payload.get('records')
        if not isinstance(records, list) or not records:
            return self._json({'ok': False, 'error': _('Debe enviar una lista records no vacía.')}, status=422)
        if len(records) > MAX_BATCH_RECORDS:
            return self._json({'ok': False, 'error': _('El lote supera el máximo de %s entregas.', MAX_BATCH_RECORDS)}, status=422)
        results = []
        for data in records:
            if not isinstance(data, dict):
                results.append({'ok': False, 'error': _('Entrega inválida.')})
                continue
            try:
                with request.env.cr.savepoint():
                    results.append(self._sync_record(data))
            except (AccessError, UserError, ValidationError, ValueError) as exc:
                results.append({'client_uuid': data.get('client_uuid') or data.get('id'), 'ok': False, 'error': str(exc)})
        return self._json({
            'ok': all(item.get('ok') for item in results),
            'results': results,
            'server_time': self._server_time(),
        }, status=200)
