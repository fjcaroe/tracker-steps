"""Exercise the original installed Steps transport models in a throwaway, offline native restore."""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from lxml import etree
from odoo.modules.module import get_module_path


def probe(env, *, check_pricelist=False):
    assert re.fullmatch(r'(?:MANAGEMENT_QA|COMMUNITY)_STEPS_TRANSPORT_[A-Z0-9_]{1,30}', env.cr.dbname)
    if env.cr.dbname.startswith('COMMUNITY_'):
        assert check_pricelist
        installed = env['ir.module.module'].search([('state', '=', 'installed')])
        assert 'product' in installed.mapped('name') and not installed.filtered(lambda m: m.license == 'OEEL-1')
    assert Path(get_module_path('steps_transport')).resolve() == Path('/opt/odoo18/custom_addons/steps_transport')
    operator = env['res.users'].browse(7)
    assert operator.active and operator.has_group('base.group_user') and not operator.has_group('base.group_system')
    company = operator.company_id
    scope = env(user=operator.id, su=False, context={'allowed_company_ids': [company.id]})
    route_model = scope['steps.transport.route']
    line_model = scope['steps.transport.route.line']
    assert not route_model.env.su
    for model in (route_model, line_model):
        for operation in ('create', 'read', 'write', 'unlink'):
            model.check_access(operation)
    assert route_model.search_count([]) == line_model.search_count([]) == 0
    form = etree.fromstring(route_model.get_view(view_type='form')['arch'].encode())
    exposed = set(form.xpath('//field/@name'))
    assert form.tag == 'form' and 'name' in exposed
    employee = scope['hr.employee'].search([('company_id', '=', company.id)], limit=1)
    assert employee
    assert not scope['fleet.vehicle'].search([], limit=1)

    route = route_model.create({'route_desc': 'Ensayo privado de transporte'})
    assert route.name and route.name != 'Nuevo'
    assert route.operation == 'entry' and route.date and route.company_id == company
    assert route.responsible_id.id == operator.id
    if check_pricelist:
        master = scope['product.pricelist'].search([('company_id', 'in', [False, company.id])],
                                                   order='id', limit=1)
        assert master and route_model._fields['pricelist_id'].comodel_name == master._name
        master.check_access('read')
        route.write({'pricelist_id': master.id})
        route.flush_recordset(['pricelist_id'])
        route.invalidate_recordset(['pricelist_id'])
        assert route.pricelist_id == master
        env.cr.execute('SELECT pricelist_id FROM steps_transport_route WHERE id=%s', [route.id])
        assert env.cr.fetchone() == (master.id,)
    start = datetime.combine(route.date, datetime.min.time()).replace(hour=8)
    line = line_model.create({'route_id': route.id, 'employee_id': employee.id,
                              'seat': 1, 'boarded_at': start})
    assert line in route.line_ids and line.sequence == 1
    line.write({'alighted_at': start + timedelta(minutes=30)})
    route.write({'operation': 'exit'})
    assert line.alighted_at > line.boarded_at and route.operation == 'exit'
    env.flush_all()
    route_id, line_id = route.id, line.id
    route.unlink()
    line.invalidate_recordset()
    assert not route_model.browse(route_id).exists() and not line_model.browse(line_id).exists()
    env.cr.rollback()
    assert route_model.search_count([]) == line_model.search_count([]) == 0
    result = {
        'uid': operator.id, 'generated_form_fields': sorted(exposed), 'operator_is_system': False,
        'existing_employee_selected': True, 'vehicle_available': False, 'sequence_assigned': True,
        'entry_exit_and_timestamps': True, 'cascade_delete': True, 'rolled_back': True,
    }
    if check_pricelist:
        result['original_pricelist_selected'] = True
    print(('STEPS_TRANSPORT_COMMUNITY=' if env.cr.dbname.startswith('COMMUNITY_') else
           'STEPS_TRANSPORT_NATIVE=') + json.dumps(result))


if 'env' in globals():
    probe(env, check_pricelist=globals().get('check_pricelist', False))
