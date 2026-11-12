"""Read-only dispatch baseline for T207/T208; no business writes."""
import json
from odoo import fields

companies = env['res.company'].search([('id', 'child_of', env.context.get('inspect_company_id', env.company.id))])
result = {'types': env['step.freight.dispatch.type'].search([]).read(['name', 'company_ids']),
    'companies': companies.read(['name', 'parent_id', 'partner_id']),
    'warehouses': env['stock.warehouse'].search([('company_id', 'in', companies.ids)]).read(['name', 'company_id', 'lot_stock_id', 'in_type_id', 'out_type_id']),
    'receipts': env['stock.picking'].search([('name', 'in', env.context.get('inspect_receipt_names', []))]).read(['name', 'state', 'company_id', 'step_fruit_reversal_id', 'return_id']),
    'partner_flags': {n:f.string for n,f in env['res.partner']._fields.items() if any(s in n for s in ('customer','cliente','productor'))},
    'lot_company_required': env['stock.lot']._fields['company_id'].required}
print('T207_BASELINE '+json.dumps(result, default=str))
env.cr.rollback()
