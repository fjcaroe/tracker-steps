"""T169 native accounting form, journal list and branch availability."""
import importlib
import json
from pathlib import Path
from lxml import etree
from native_business_profile import scoped_business_environment

try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    scoped=scoped_business_environment(env)
    journals=scoped['account.journal'].search([('company_id','=',scoped.company.id)])
    assert journals
    visible=scoped['ir.ui.menu']._visible_menu_ids()
    actions=scoped['ir.actions.act_window'].search([('res_model','=','account.journal')])
    menus=scoped['ir.ui.menu'].search([('action','in',['ir.actions.act_window,%s'%a.id for a in actions])])
    assert set(menus.ids)&visible
    for kind,view in [('form','account.view_account_journal_form'),('list','account.view_account_journal_tree')]:
        arch=etree.fromstring(journals.get_view(view_id=scoped.ref(view).id,view_type=kind)['arch'])
        assert arch.xpath("//field[@name='step_available_branch_ids']")
    branches=scoped['res.company'].search([('id','child_of',scoped.company.id),('id','!=',scoped.company.id),('id','in',scoped.user.company_ids.ids)])
    assert journals[:1].step_available_branch_ids==branches
    if branches:
        branch_scope=scoped(context=dict(scoped.context,allowed_company_ids=branches[:1].ids))
        assert journals[:1].id in branch_scope['account.journal'].search([]).ids
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket':169,'versions':EXPECTED,'native_form_and_list':True,
          'company':scoped.company.id,'available_branches':branches.ids,'business_profile':scoped.uid}))
finally:
    env.cr.rollback()
