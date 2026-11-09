"""Verify all six existing Activities menus without writing to the destination."""
import importlib
import json
from pathlib import Path

from odoo.exceptions import AccessError
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
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
        'ticket': 179, 'versions': EXPECTED, 'existing_profile': scopes[0].uid,
        'menus_and_forms': len(MENU_NAMES), 'records_by_company': counts, 'writes': False,
    }))
finally:
    env.cr.rollback()
