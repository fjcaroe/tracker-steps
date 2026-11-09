"""Verify all six existing Activities menus without writing to the destination."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

from lxml import etree
from odoo.exceptions import AccessError, UserError
from odoo.tools.safe_eval import safe_eval
from native_business_profile import scoped_business_environment


MENU_NAMES = (
    'menu_hr_salary_custom', 'menu_step_tarja', 'menu_step_tarja_cost',
    'menu_hr_salary_contratista', 'menu_step_tarja_contra', 'menu_step_tarja_costo_contra',
)


def verify_scope(scoped):
    company = scoped.company
    visible = scoped['ir.ui.menu']._visible_menu_ids()
    count = 0
    for name in MENU_NAMES:
        menu = scoped.ref('step_hr.' + name)
        assert menu.id in visible, name
        action = menu.action._get_action_dict()
        assert action['res_model'] in ('hr.salary.custom', 'step.tarja'), action
        model = scoped[action['res_model']]
        domain = safe_eval(action['domain'] or '[]')
        records = model.search(domain)
        expected = model.sudo().search([*domain, ('company_id', '=', company.id)])
        assert set(records.ids) == set(expected.ids), (name, company.id)
        count += len(records)
        views = {kind: view_id for view_id, kind in action['views']}
        for kind in ('list', 'form'):
            assert model.get_view(view_id=views[kind], view_type=kind)['arch'], name
        if records:
            assert records[:1].read(['company_id'])[0]['company_id'][0] == company.id
        other = model.sudo().search([*domain, ('company_id', '!=', company.id)], limit=1)
        if other:
            try:
                model.browse(other.id).read(['company_id'])
            except AccessError:
                pass
            else:
                raise AssertionError('A direct link exposed a record from another company')
    return count


def verify_cost_centers(scoped):
    tarjas = scoped['step.tarja']
    form = tarjas.get_view(view_id=scoped.ref('step_hr.view_step_tarja_form').id, view_type='form')
    nodes = etree.fromstring(form['arch']).xpath("//list/field[@name='cost_id']")
    assert len(nodes) == 3
    company = scoped.company
    context = {'parent': SimpleNamespace(company_id=company.id, pricelist_id=False),
               'cost_id_domain': []}
    accounts = scoped['account.analytic.account']
    expected = accounts.search([
        ('company_id', '=', company.id), ('active', '=', True),
        ('root_plan_id.name', 'in', ['Centro de costos', 'Centro Costos']),
    ])
    for node in nodes:
        context['parent'].pricelist_id = False
        domain = safe_eval(node.get('domain'), context)
        assert {item[0] for item in accounts.name_search(args=domain, limit=None)} == set(expected.ids)
        context['parent'].pricelist_id = 1
        assert safe_eval(node.get('domain'), context) == [('id', 'in', [])]
    example = tarjas.search([('pricelist_id', '=', False), ('tarja_line', '!=', False)], limit=1, order='id desc')
    if company.name == 'EcoPlantas':
        assert example and expected, 'The reported no-tariff form and cost center catalog must be available'
    if example:
        assert example.company_id == company and example.tarja_line.read(['cost_id'])
    return {'centers': len(expected), 'existing_no_tariff': bool(example)}


def verify_accounting_form(scoped):
    tarjas = scoped['step.tarja']
    form = tarjas.get_view(view_id=scoped.ref('step_hr.view_step_tarja_form').id, view_type='form')
    assert etree.fromstring(form['arch']).xpath("//button[@name='action_conta']")
    incomplete = tarjas.new({'company_id': scoped.company.id, 'tarja_type': 'propio', 'date': False})
    try:
        incomplete._step_daily_accounting_scope()
    except UserError as error:
        assert 'Agregue al menos una línea' in str(error), str(error)
    else:
        raise AssertionError('The incomplete task should fail preflight')


def verify_contractor_worker_form(scoped):
    crews = scoped['hr.salary.custom']
    form = crews.get_view(view_id=scoped.ref('step_hr.view_hr_salary_custom_form').id, view_type='form')
    fields = etree.fromstring(form['arch']).xpath("//field[@name='contract_line']/list/field")
    assert not [field for field in fields if field.get('name') == 'employee_id_domain']
    worker, = [field for field in fields if field.get('name') == 'employee_id']
    parent = SimpleNamespace(company_id=scoped.company.id, partner_id=False)
    assert safe_eval(worker.get('domain'), {'parent': parent}) == [('id', '=', False)]
    parent.partner_id = 1
    domain = safe_eval(worker.get('domain'), {'parent': parent})
    assert ('company_id', '=', scoped.company.id) in domain
    assert ('contratista_id', '=', parent.partner_id) in domain


try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    is_development = env.cr.dbname == 'LAB_TAREAS' or env.cr.dbname.startswith('MANAGEMENT_QA_DEVELOPMENT_')
    if is_development:
        main = env.ref('base.main_company')
        demo = env['res.company'].search([('name', '=', 'EcoPlantas')])
        assert len(demo) == 1
        reviewers = env['res.users'].search([
            ('share', '=', False), ('id', '!=', 1),
            ('company_ids', 'in', main.ids), ('company_ids', 'in', demo.ids),
        ])
        reviewer = reviewers.filtered(lambda user: user.has_group('base.group_system'))[:1]
        assert reviewer, 'An existing reviewer must have access to both reported companies'
        first, second = main.id, demo.id
        scopes = [env(user=reviewer, su=False, context=dict(env.context, allowed_company_ids=ids))
                  for ids in ([first, second], [second, first])]
    else:
        scopes = [scoped_business_environment(env)]
    counts = {scope.company.id: verify_scope(scope) for scope in scopes}
    cost_centers = {}
    version = tuple(map(int, EXPECTED['step_activities_company'].split('.')))
    if version >= (18, 0, 1, 1, 0):
        if not is_development:
            scoped = scopes[0]
            allowed = scoped.user.company_ids
            owners = scoped['step.tarja'].sudo().search([('company_id', 'in', allowed.ids)]).company_id
            scopes += [scoped(context=dict(scoped.context, allowed_company_ids=(owner | allowed).ids))
                       for owner in owners - scoped.company]
        cost_centers = {scope.company.id: verify_cost_centers(scope) for scope in scopes}
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
        'ticket': 179, 'versions': EXPECTED, 'existing_profile': scopes[0].uid,
        'menus_and_forms': len(MENU_NAMES), 'records_by_company': counts, 'writes': False,
    }))
    if cost_centers:
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 182, 'cost_center_selectors': cost_centers}))
    if version >= (18, 0, 1, 2, 0):
        for scope in scopes:
            verify_accounting_form(scope)
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 183, 'accounting_preflight': True}))
    if version >= (18, 0, 1, 3, 0):
        for scope in scopes:
            verify_contractor_worker_form(scope)
        print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 184, 'contractor_worker_form': True}))
finally:
    env.cr.rollback()
