"""Read native company families with multiple warehouse-bearing plants for UI QA."""
import json
try:
    assert env.cr.dbname == 'LAB_TAREAS'
    companies = env['stock.warehouse'].search([]).company_id
    roots = companies.root_id
    rows = []
    for root in roots:
        family = companies.filtered(lambda company:company.root_id == root)
        if len(family) > 1:
            rows.append({'root':root.id,'plants':family.read(['name','parent_id'])})
    print('INTERPLANT_QA_FAMILIES '+json.dumps(rows))
finally:
    env.cr.rollback()
