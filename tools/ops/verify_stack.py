"""Run real product probes and effective forms; rollback every sample."""
import importlib
import json
from pathlib import Path

versions = dict(EXPECTED)
root = ROOT
env = env(context=dict(env.context, no_reset_password=True, mail_notify_force_send=False,
                       mail_auto_subscribe_no_notify=True))
for name, version in versions.items():
    module = env['ir.module.module'].search([('name','=',name)])
    assert module.state=='installed' and module.latest_version==version, (name,module.latest_version)
    assert importlib.import_module('odoo.addons.'+name).__file__.startswith(root+'/'), name

probes = [
    ('verify_freight.py', {'ROOT':root,'EXPECTED':versions['step_operations_ui'],
                         'EXPECTED_ALL':{name:versions[name] for name in ('step_operations_ui','step_dispatch_guide')}}),
    ('verify_export_navigation.py', {'ROOT':root,'EXPECTED':{'step_export':versions['step_export']}}),
    ('verify_packing_revision.py', {'ROOT':root,'EXPECTED':{'step_packing_operations':versions['step_packing_operations']}}),
    ('verify_fruit_reception.py', {'ROOT':root,'EXPECTED':{'step_inventory_packing':versions['step_inventory_packing']}}),
    ('verify_producer_revision.py', {'ROOT':root,'EXPECTED':{name:versions[name] for name in
        ('step_producers','step_producer_fruit_flow','step_export','step_producers_integrations')}}),
    ('verify_settings_navigation.py', {'ROOT':root,'EXPECTED':{name:versions[name] for name in ('step_account_treasury_batch','step_dispatch_guide')}}),
    ('verify_home_heading.py', {'ROOT':root,'EXPECTED':{'step_demo_homepage':versions['step_demo_homepage']}}),
    ('verify_payroll.py', {'EXPECTED_DATABASE':env.cr.dbname,'EXPECTED_ROOT':root,
        'EXPECTED_VERSIONS':{name:version for name,version in versions.items() if name.startswith('step_hr') or name in ('step_environment_policy','step_payroll_engine_transition')}}),
]
for filename, values in probes:
    scope={'env':env, **values}
    path=Path(__file__).resolve().parent/filename
    # exec in Odoo shell does not define __file__; runner supplies the ops path.
    exec(compile(path.read_text(),str(path),'exec'),scope)
    env.invalidate_all()
    print('STACK_PRODUCT_OK '+filename)

checked=[]
for menu_id, parent_id in (
    ('menu_step_phyto_restriction_bpa','menu_bpa_operations'),
    ('menu_step_phyto_restriction_bpa_history','menu_bpa_analytics'),
):
    menu=env.ref('step_agro_traceability.'+menu_id)
    assert menu.parent_id==env.ref('step_bpa_irrigation.'+parent_id)
    assert menu.action and menu.action.res_model=='step.phyto.restriction'
env['step.phyto.restriction'].get_view(view_type='form')
print('STACK_BPA_NATIVE_MENU_OK')
for model in ('res.partner','sale.order','purchase.order','account.move','account.payment',
              'stock.picking','stock.quant.package','project.task','project.project',
              'fleet.vehicle','step.management.estimation','step.management.budget.line'):
    env[model].get_view(view_type='form')
    checked.append(model)
print('STACK_FLOW_OK '+json.dumps({'versions':versions,'effective_forms':checked,'sample_records':'rolled back'}))
env.cr.rollback()
