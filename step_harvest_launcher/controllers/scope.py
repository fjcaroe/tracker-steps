"""Bind Harvest reads and pending uploads to their native database and company."""
import hashlib
import hmac
import json

from odoo import http, _
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.addons.step_cosecha.controllers.harvest_api import StepHarvestApi


def scope_token(database, database_uuid, user_id, company_id):
    identity = json.dumps([database, database_uuid, user_id, company_id], separators=(',', ':'))
    return hashlib.sha256(identity.encode()).hexdigest()


def environment_scope(env):
    uuid = env['ir.config_parameter'].sudo().get_param('database.uuid', '')
    return scope_token(env.cr.dbname, uuid, env.uid, env.company.id)


class ScopedHarvestApi(StepHarvestApi):
    def _active_company(self):
        """HTTP routes retain the native web client's selected company cookie."""
        raw = request.httprequest.cookies.get('cids')
        if not request.session.uid or not raw:
            return None
        try:
            selected = [int(value) for value in raw.replace(',', '-').split('-')]
            allowed = request.env.user.company_ids.ids
            if not selected or any(value not in allowed for value in selected):
                raise ValueError('Company not allowed')
            request.update_context(allowed_company_ids=list(dict.fromkeys(selected)))
        except (ValueError, TypeError):
            return self._json({'ok': False, 'error': _(
                'La empresa seleccionada ya no está disponible. Revise la selección en Odoo.')}, status=403)
        return None

    @http.route()
    def health(self, **kwargs):
        error = self._active_company()
        return error if error is not None else super().health(**kwargs)

    @http.route()
    def session(self, **kwargs):
        error = self._active_company()
        return error if error is not None else super().session(**kwargs)

    @http.route()
    def bootstrap(self, **kwargs):
        error = self._active_company()
        return error if error is not None else super().bootstrap(**kwargs)

    @http.route()
    def reference(self, resource, **kwargs):
        error = self._active_company()
        return error if error is not None else super().reference(resource, **kwargs)

    def _native_record(self, model, identifier, shared=False):
        if not str(identifier or '').isdigit():
            raise ValidationError(_('Seleccione un registro del maestro de esta empresa.'))
        record = request.env[model].browse(int(identifier)).exists()
        if not record:
            raise ValidationError(_('El registro seleccionado ya no está disponible.'))
        record.check_access('read')
        if 'company_ids' in record._fields:
            if record.company_ids and request.env.company not in record.company_ids:
                raise ValidationError(_('El maestro seleccionado no está habilitado para esta empresa.'))
        elif 'company_id' in record._fields and record.company_id != request.env.company and not (shared and not record.company_id):
            raise ValidationError(_('El registro seleccionado pertenece a otra empresa.'))
        return record

    def _reference_data(self, resource, query=None, limit=None):
        if resource not in ('varieties', 'cost_centers'):
            return super()._reference_data(resource, query, limit)
        company = request.env.company
        if resource == 'varieties':
            model = request.env['step.variedad']
            domain = (['|', ('company_ids', '=', False), ('company_ids', 'in', company.ids)]
                      if 'company_ids' in model._fields else [('company_id', 'in', [False, company.id])])
        else:
            model = request.env['account.analytic.account']
            domain = [('company_id', 'in', [False, company.id])]
            plan = company.management_actual_center_plan_id if 'management_actual_center_plan_id' in company._fields else False
            domain += ([('root_plan_id', '=', plan.id)] if plan else
                       [('root_plan_id.name', 'in', ['Centro de costos', 'Centro Costos', 'Centro de Costos'])])
        if query:
            domain.append(('name', 'ilike', query))
        records = model.search(domain, order='name,id', limit=max(1, min(int(limit or 500), 5000)))
        if resource == 'varieties':
            return [self._item(record, species=record.especie_id.display_name if record.especie_id else '') for record in records]
        return [self._item(record, farm_id=record.fundo_id.id if record.fundo_id else False,
                           variety_id=record.variedad_id.id if record.variedad_id else False) for record in records]

    def _get_or_create_order(self, data):
        values = data.get('work_order') if isinstance(data.get('work_order'), dict) else {}
        if values.get('odoo_id'):
            return self._native_record('step.cosecha.registry', values['odoo_id'])
        reference = str(values.get('id') or '').strip()
        if not reference:
            raise ValidationError(_('La entrega requiere una jornada identificada.'))
        model = request.env['step.cosecha.registry']
        existing = model.search([('company_id', '=', request.env.company.id),
            '|', ('mobile_work_order', '=', reference), ('folio', '=', reference)], limit=2)
        if len(existing) > 1:
            raise ValidationError(_('Hay varias jornadas con esa referencia. Seleccione la jornada de Odoo.'))
        if existing:
            return existing
        farm = self._native_record('step.fundo', values.get('farm_id'))
        variety = self._native_record('step.variedad', values.get('variety_id'), shared=True)
        center = self._native_record('account.analytic.account', values.get('cost_id'), shared=True)
        crew = self._native_record('hr.salary.custom', values.get('crew_id'))
        kind = crew.group_type
        if kind not in ('propio', 'contratista'):
            raise ValidationError(_('La cuadrilla requiere su tipo propio o contratista.'))
        if kind == 'contratista' and not crew.partner_id:
            raise ValidationError(_('Configure el contratista en la cuadrilla antes de registrar la cosecha.'))
        return model.create({
            'name': reference, 'folio': reference, 'mobile_work_order': reference,
            'mobile_uid': str(values.get('client_uuid') or '') or False, 'mobile_status': 'progress',
            'type_tarea': kind, 'product_uom_id': request.env.ref('uom.product_uom_kgm').id,
            'date': self._event_datetime(data.get('event_datetime')),
            'company_id': request.env.company.id, 'responsable_id': request.env.uid,
            'fundo_id': farm.id, 'variedad_id': variety.id, 'cost_id': center.id,
            'partner_id': crew.partner_id.id if kind == 'contratista' else False,
            'salary_id' if kind == 'propio' else 'salary_id_contrac': crew.id,
        })

    def _sync_record(self, data):
        values = dict(data)
        if str(values.get('worker_id') or '').isdigit():
            worker = self._native_record('hr.employee', values['worker_id'], shared=True)
        else:
            workers = request.env['hr.employee'].search([
                ('pin', '=', str(values.get('nip') or '')),
                ('company_id', 'in', [False, request.env.company.id])], limit=2)
            if len(workers) != 1:
                raise ValidationError(_('Seleccione un trabajador existente con identificación única en esta empresa.'))
            worker = workers
        existing = request.env['step.cosecha.tarja.registry.line'].search([
            ('mobile_uid', '=', str(values.get('client_uuid') or values.get('id') or ''))], limit=1)
        if existing and existing.registry_id.company_id != request.env.company:
            raise ValidationError(_('La entrega ya existe en otro contexto. No se traslada de empresa.'))
        values['worker_id'] = worker.id
        return super()._sync_record(values)

    def _json(self, payload, status=200):
        payload = dict(payload)
        payload['scope'] = environment_scope(request.env) if request.session.uid else False
        if request.session.uid and 'company' in payload:
            # Public controllers use the actual request company, just like
            # bootstrap and sync, rather than the user's default company.
            payload['company'] = {'id': request.env.company.id, 'name': request.env.company.display_name}
        if 'capabilities' in payload:
            payload['capabilities'] = [*payload['capabilities'], 'context_scope']
        return super()._json(payload, status=status)

    @http.route()
    def sync(self, **kwargs):
        error = self._active_company()
        if error is not None:
            return error
        expected = self._payload().get('scope')
        if not isinstance(expected, str) or not hmac.compare_digest(expected, environment_scope(request.env)):
            return self._json({'ok': False, 'error': _(
                'La sesión o la empresa cambió. Actualice Harvest antes de sincronizar. '
                'Los pendientes siguen guardados en su contexto original.')}, status=409)
        return super().sync(**kwargs)
