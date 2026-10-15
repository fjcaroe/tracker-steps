"""Read-only Odoo-shell diagnosis of analytic requirements on selected draft entries.
Set REFERENCES to the exact entry references before executing this script.
"""
import json
from odoo.exceptions import ValidationError
try:
    moves=env['account.move'].search([('ref','in',REFERENCES)])
    rules=env['account.analytic.applicability']
    rule_fields=[n for n in rules._fields if n not in ('__last_update','display_name') and
        n in ('analytic_plan_id','business_domain','applicability','company_id','account_prefix','account_type','account_type_ids','product_categ_id')]
    output={'moves':[],'plans':env['account.analytic.plan'].search([]).read(['name','parent_id','default_applicability']),
        'rules':rules.search([]).read(rule_fields),'rule_fields':rule_fields}
    for move in moves:
        row={'id':move.id,'name':move.name,'ref':move.ref,'state':move.state,'company':move.company_id.display_name,'lines':[]}
        for line in move.line_ids:
            args={'company_id':line.company_id.id,'account':line.account_id.id,'product':line.product_id.id,'business_domain':'general'}
            try:
                line.with_context(validate_analytic=True)._validate_analytic_distribution()
                failure=False
            except ValidationError as error:
                failure=str(error)
            row['lines'].append({'id':line.id,'account_id':line.account_id.id,'account':line.account_id.display_name,
                'type':line.account_id.account_type,'balance':line.balance,'distribution':line.analytic_distribution,
                'display_type':line.display_type,'error':failure,
                'plans':env['account.analytic.plan'].with_company(line.company_id).get_relevant_plans(**args)})
        output['moves'].append(row)
    print('OPENING_DIAGNOSIS '+json.dumps(output,ensure_ascii=True))
finally:
    env.cr.rollback()
