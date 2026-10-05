"""Read-only accounting application inventory; never reads business records."""
import json
from inspect_sys import query

print(query('SyS', "SELECT name,latest_version FROM ir_module_module WHERE state='installed' "
            "AND (name LIKE 'account%' OR name LIKE '%treasury%' OR name LIKE '%factur%' "
            "OR name LIKE '%sii%') ORDER BY name"))
print(query('SyS', "SELECT d.module,d.name,m.name FROM ir_model_data d "
            "JOIN ir_ui_menu m ON d.model='ir.ui.menu' AND d.res_id=m.id "
            "WHERE d.module IN ('step_account_treasury','account') "
            "ORDER BY d.module,d.name"))
print(json.dumps({'home_views': query('SyS', "SELECT id,key,website_id,md5(arch_db::text) "
            "FROM ir_ui_view WHERE key='website.homepage' OR key LIKE 'step_demo_homepage.%' "
            "ORDER BY id")}))
