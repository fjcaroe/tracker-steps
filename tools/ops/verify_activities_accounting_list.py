import importlib
import json
from pathlib import Path

from lxml import etree
from odoo.tools.safe_eval import safe_eval

from native_business_profile import scoped_business_environment


def verify_accounting_list(scoped):
    menu = scoped.ref('step_hr.menu_acount_propio')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    assert menu.action == scoped.ref('step_hr.action_move_journal_step_propio')
    action = menu.action._get_action_dict()
    assert action['res_model'] == 'account.move'
    model = scoped['account.move']
    domain = safe_eval(action['domain'], dict(scoped.context))
    expected = model.search([('propio', '=', True), ('company_id', '=', scoped.company.id)])
    result = model.search(domain)
    assert set(result.ids) == set(expected.ids), scoped.company.id
    assert ('company_id', '=', scoped.company.id) in domain and ('propio', '=', True) in domain
    views = {kind: view_id for view_id, kind in action['views']}
    for kind in ('list', 'form'):
        arch = etree.fromstring(model.get_view(view_id=views[kind], view_type=kind)['arch'])
        assert arch.tag == kind
    if result:
        assert result[0].read(['company_id', 'journal_id', 'state'])[0]['company_id'][0] == scoped.company.id
    return len(result)


try:
    module, version = next(iter(EXPECTED.items()))
    assert module == 'step_activities_accounting_company'
    installed = env['ir.module.module'].search([('name', '=', module), ('state', '=', 'installed')])
    assert installed.latest_version == version
    assert Path(importlib.import_module('odoo.addons.' + module).__file__).resolve().parent == Path(ROOT) / module
    development = env.cr.dbname == 'LAB_TAREAS' or env.cr.dbname.startswith('MANAGEMENT_QA_DEVELOPMENT_')
    scoped = scoped_business_environment(env)
    scopes = [scoped]
    if development:
        main = scoped.company
        eco = env['res.company'].search([('name', '=', 'EcoPlantas')])
        assert len(eco) == 1
        reviewers = env['res.users'].search([
            ('active', '=', True), ('share', '=', False), ('id', '!=', 1),
            ('company_ids', 'in', main.ids), ('company_ids', 'in', eco.ids),
        ])
        reviewer = reviewers.filtered(lambda user: user.has_group('account.group_account_manager'))[:1]
        assert reviewer
        scopes = [env(user=reviewer, su=False, context=dict(env.context, allowed_company_ids=ids))
                  for ids in ([eco.id, main.id], [main.id, eco.id])]
        assert len(scopes[0]['account.move'].search([('propio', '=', True)]).company_id) >= 2
    results = {scope.company.id: verify_accounting_list(scope) for scope in scopes}
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
        'ticket': 191, 'version': version, 'menu_list_form': True,
        'entries_by_active_company': results, 'multiple_selected': development,
    }))
finally:
    env.cr.rollback()
