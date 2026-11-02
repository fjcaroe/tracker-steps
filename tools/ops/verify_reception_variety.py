"""T152 effective native menus/forms; stock writes only in private copies."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    from preserve_fruit_constraints import LEGACY, CANONICAL
    for table, column in LEGACY:
        env.cr.execute("SELECT target.relname,c.convalidated FROM pg_constraint c JOIN pg_class source ON source.oid=c.conrelid JOIN pg_class target ON target.oid=c.confrelid JOIN pg_attribute a ON a.attrelid=source.oid AND a.attnum=ANY(c.conkey) WHERE c.contype='f' AND source.relname=%s AND a.attname=%s", (table,column))
        assert env.cr.fetchall() == [(CANONICAL, True)]
    print('MANAGEMENT_CANONICAL_FRUIT_FKS_OK')
    scoped = scoped_business_environment(env)
    previous = config['test_enable']; config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    for kind, menu_ref, view_ref in (
        ('process', 'step_packing_operations.menu_packing_reception_process', 'step_packing_reception_revision.view_process_reception_form'),
        ('packed', 'step_packing_operations.menu_packing_reception_packed', 'stock.view_picking_form')):
        menu = scoped.ref(menu_ref)
        assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
        action = scoped.ref('step_inventory_packing.action_steps_fruit_%s_reception' % kind)
        assert menu.action == action
        arch = etree.fromstring(scoped['stock.picking'].get_view(view_id=scoped.ref(view_ref).id, view_type='form')['arch'])
        columns = arch.xpath("//field[@name='fruit_tag_line_ids']/list/field/@name")
        assert columns[columns.index('product_id') + 1] == 'variety_id', columns
        header = arch.xpath("//page[@name='step_packing_fruit']//field[@name='fruit_variety_id']")
        assert header and "step_fruit_reception_kind in ('process','packed')" in header[0].get('invisible', '')
        field = arch.xpath("//field[@name='fruit_tag_line_ids']/list/field[@name='variety_id']")[0]
        assert 'parent.fruit_species_id' in field.get('domain', '')
        record = scoped['stock.picking'].search([('step_fruit_reception_kind', '=', kind)], limit=1)
        Form(record or scoped['stock.picking'].with_context(default_step_fruit_reception_kind=kind), view=view_ref)
    clone_flow = env.cr.dbname.startswith('MANAGEMENT_QA_')
    if clone_flow:
        from probe_reception_flow import verify_flow
        verify_flow(env, scoped, row_varieties=True)
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket':152, 'versions':EXPECTED,
        'existing_profile':scoped.uid, 'company_id':scoped.company.id,
        'native_menu_and_form':True, 'clone_flow':clone_flow,
        'variety_after_product':True, 'process_and_packed':True, 'writes':False}))
finally:
    env.cr.rollback()
