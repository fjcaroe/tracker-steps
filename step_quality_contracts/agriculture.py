"""The existing Steps inspection/advisory overview, independent of either engine."""
from odoo import fields
from odoo.exceptions import AccessError


def inspection_summary(env, period_domain):
    empty = {'available': False, 'total': 0, 'created': 0, 'executed': 0,
        'approved': 0, 'overdue': 0, 'recent': []}
    if 'step.agriculture.inspection' not in env:
        return empty
    model = env['step.agriculture.inspection'].sudo(False)
    try:
        model.check_access('read')
        model.check_field_access_rights('read', ['name', 'state', 'fecha_a_ejecutar', 'date',
            'fundo_id', 'asignado_a_id', 'responsable_id', 'create_date'])
        recent = [{'id': record.id, 'name': record.name or 'Inspección interna', 'state': record.state or 'status1',
            'date': fields.Date.to_string(record.fecha_a_ejecutar or record.date),
            'farm': record.fundo_id.display_name or 'Sin fundo',
            'responsible': record.asignado_a_id.display_name or record.responsable_id.display_name or 'Sin asignar'}
            for record in model.search(period_domain, order='fecha_a_ejecutar desc, create_date desc', limit=6)]
        return {'available': True, 'total': model.search_count(period_domain),
            'created': model.search_count(period_domain + [('state', '=', 'status1')]),
            'executed': model.search_count(period_domain + [('state', '=', 'status2')]),
            'approved': model.search_count(period_domain + [('state', '=', 'status3')]),
            'overdue': model.search_count(period_domain + [('state', '=', 'status1'),
                ('fecha_a_ejecutar', '<', fields.Date.context_today(model))]), 'recent': recent}
    except AccessError:
        return empty


def advisor_summary(env, period_domain):
    if 'step.agriculture.advisory' not in env:
        return {'available': False, 'total': 0, 'pending': 0}
    model = env['step.agriculture.advisory'].sudo(False)
    try:
        model.check_access('read')
        model.check_field_access_rights('read', ['state', 'create_date'])
        return {'available': True, 'total': model.search_count(period_domain),
            'pending': model.search_count(period_domain + [('state', '=', 'status1')])}
    except AccessError:
        return {'available': False, 'total': 0, 'pending': 0}
