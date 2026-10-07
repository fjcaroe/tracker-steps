"""Read APR field ownership and effective export sales form without private values."""
import inspect
import json
from lxml import etree

try:
    fields = ['cod_medidor', 'sector_id', 'carga_type', 'p_desde', 'p_hasta',
              'anterior_apr', 'actual_apr', 'consumo_apr']
    order = env['sale.order']
    for field in fields:
        definition = order._fields.get(field)
        if definition:
            print('FIELD', field, definition.string, definition.type)
    for model, names in [('sale.order', fields), ('res.company', ['product_fijo', 'product_consu'])]:
        for cls in type(env[model]).__mro__:
            if any(name in cls.__dict__ for name in names):
                print('OWNER', model, inspect.getfile(cls))
    for view in env['ir.ui.view'].search([('model', '=', 'sale.order'), ('arch_db', 'ilike', 'consumo_apr')]):
        print('APR_VIEW', view.id, view.name, view.get_external_id().get(view.id), view.arch_db)
    tree = etree.fromstring(order.get_view(view_type='form')['arch'].encode())
    for node in tree.xpath('//field'):
        if node.get('name') in fields or node.get('name') in ('product_id', 'product_template_id'):
            print('EFFECTIVE', json.dumps(dict(node.attrib)))
    for company in env['res.company'].search([]):
        print('APR_CONFIGURATION', company.id, {name: bool(company[name]) for name in ('product_fijo', 'product_consu') if name in company._fields})
    module = env['ir.module.module'].search([('name', '=', 'step_export')])
    import odoo.addons.step_export
    print('RUNTIME', module.latest_version, odoo.addons.step_export.__file__)
finally:
    env.cr.rollback()
