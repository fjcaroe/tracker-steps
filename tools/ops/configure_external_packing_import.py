"""Configure the approved external Packing template from a private plan.

Run with Odoo shell in an approved Cerro copy or in Cerro under the shared lease.
The caller supplies PLAN and MODE. Copy and verification runs roll back.
"""
import json

from odoo.addons.step_packing_ticket_revision.external_reception import normalized

if MODE == 'copy':
    assert env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_t193')
else:
    assert MODE in ('apply', 'verify') and env.cr.dbname == 'CERRO_EL_PLOMO'

company = env['res.company'].browse(PLAN['company']).exists()
assert company.name == PLAN['company_name']
operator = env['res.users'].browse(PLAN['operator']).exists()
assert company in operator.company_ids and operator.has_group('stock.group_stock_manager')
scope = env(user=operator, su=False, context=dict(env.context, allowed_company_ids=company.ids,
            tracking_disable=True, mail_create_nosubscribe=True, mail_notify_force_send=False))
module = scope['ir.module.module'].sudo().search([('name', '=', 'step_packing_ticket_revision')])
assert module.state == 'installed' and module.latest_version == PLAN['version']
counts = {}


def ensure(model, domain, values):
    records = scope[model].with_context(active_test=False).search(domain, limit=2)
    assert len(records) <= 1, f'Ambiguous master in {model}'
    if records:
        if 'active' in records._fields:
            assert records.active, f'Archived master in {model}'
        return records
    assert MODE != 'verify', f'Missing configured master in {model}'
    counts[model] = counts.get(model, 0) + 1
    return scope[model].create(values)


def required_record(model, record_id):
    record = scope[model].browse(record_id).exists()
    assert record and record.has_access('read'), model
    return record


defaults = PLAN['defaults']
operation = required_record('stock.picking.type', defaults['picking_type_id'])
packing = required_record('res.partner', defaults['packing_id'])
product = required_record('product.product', defaults['product_id'])
input_packaging = required_record('product.packaging', PLAN['input_packaging'])
assert operation.company_id == company and operation.code == 'incoming'
assert packing.step_export_packing and product.default_code == PLAN['raw_product_code']
assert input_packaging.product_id == product
assert required_record('step.management.fruit.class', defaults['fruit_class_id']).category_id.id == defaults['category_id']
assert required_record('step.temporada', defaults['season_id'])
variety_base = required_record('step.variedad', PLAN['variety_base'])
species, variety_group = variety_base.especie_id, variety_base.grupo_variedad_id
assert normalized(species.name) == 'arandano' and variety_group
variety = ensure('step.variedad', [('especie_id', '=', species.id), ('name', '=ilike', PLAN['new_variety'])],
    {'name': PLAN['new_variety'], 'cod_variedad': PLAN['new_variety'],
     'especie_id': species.id, 'grupo_variedad_id': variety_group.id})
assert variety.especie_id == species

alias_values = []
for item in PLAN['farms']:
    source = item['source']
    if item.get('fundo_id'):
        farm = required_record('step.fundo', item['fundo_id'])
        assert farm.partner_id.id == item['partner_id']
    else:
        if item.get('partner_id'):
            partner = required_record('res.partner', item['partner_id'])
        else:
            partner = ensure('res.partner', [('name', '=ilike', item['partner_name']),
                             ('company_id', 'in', [False, company.id])],
                             {'name': item['partner_name'], 'is_company': True,
                              'company_id': company.id, 'is_productor': True})
        assert partner.is_productor
        farm = ensure('step.fundo', [('name', '=ilike', item['name']),
                      ('company_id', '=', company.id), ('partner_id', '=', partner.id)],
                      {'name': item['name'], 'company_id': company.id, 'partner_id': partner.id})
    alias_values.append({'kind': 'producer', 'source': source, 'source_key': normalized(source),
                         'fundo_id': farm.id})

source = PLAN['input_packaging_source']
alias_values.append({'kind': 'packaging', 'source': source, 'source_key': normalized(source),
                     'packaging_id': input_packaging.id})
for item in PLAN['output_packagings']:
    source = item['source']
    output = ensure('product.product', [('name', '=ilike', source), ('company_id', '=', company.id)],
                    {'name': source, 'company_id': company.id, 'is_storable': True,
                     'weight': item['unit_net_kg'], 'grupo_labor': 'pack'})
    assert output.is_storable and output.tracking != 'serial'
    packaging = ensure('product.packaging', [('name', '=ilike', source), ('product_id', '=', output.id)],
                       {'name': source, 'product_id': output.id, 'qty': 1, 'company_id': company.id})
    alias_values.append({'kind': 'process_packaging', 'source': source, 'source_key': normalized(source),
                         'packaging_id': packaging.id})

caliber_group = ensure('step.management.caliber.group', [
    ('company_id', '=', company.id), ('code', '=', PLAN['caliber_group_code'])],
    {'name': species.name, 'code': PLAN['caliber_group_code'], 'company_id': company.id})
for source in PLAN['calibers']:
    caliber = ensure('step.management.fruit.caliber', [('company_id', '=', company.id), ('code', '=', source)],
        {'name': source, 'code': source, 'company_id': company.id, 'group_id': caliber_group.id})
    alias_values.append({'kind': 'process_caliber', 'source': source, 'source_key': normalized(source),
                         'caliber_id': caliber.id})

template = ensure('step.external.fruit.reception.template',
                  [('name', '=', PLAN['template_name']), ('company_id', '=', company.id)],
                  dict(defaults, name=PLAN['template_name'], company_id=company.id))
assert all(template[field].id == value for field, value in defaults.items()), 'Review existing template settings'
if MODE != 'verify':
    template._remember_aliases(alias_values)
stored = {(line.kind, line.source_key): line for line in template.alias_ids}
for values in alias_values:
    alias = stored[values['kind'], values['source_key']]
    target = next(field for field in ('fundo_id', 'packaging_id', 'caliber_id') if field in values)
    assert alias[target].id == values[target]
print('T193_CONFIGURATION_OK ' + json.dumps({'mode': MODE, 'company': company.id, 'created': counts,
      'aliases': len(alias_values), 'template': template.id}), flush=True)
if MODE == 'apply':
    env.cr.commit()
elif MODE == 'verify':
    env.cr.rollback()
