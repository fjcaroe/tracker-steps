"""Private T131 reproduction; always rolls back, no branch in a live database."""
import json
from odoo.tools import config
from native_business_profile import scoped_business_environment

assert env.cr.dbname.startswith('MANAGEMENT_QA_')
previous=config['test_enable'];config['test_enable']=True
try:
    from odoo.tests import Form
    scoped=scoped_business_environment(env)
    root=scoped.company
    print('BRANCH_REPRO_PROFILE '+json.dumps({'user':scoped.uid,'company':root.id}))
    count=scoped['res.company'].search_count([])
    parent=Form(root)
    with parent.child_ids.new() as branch:
        branch.name='QA Branch Reproduction'
    parent.save()
    child=scoped['res.company'].search([('parent_id','=',root.id),('name','=','QA Branch Reproduction')])
    assert len(child)==1 and child.parent_id==root
    print('BRANCH_REPRO_CREATED '+json.dumps({'id':child.id,'parent_id':child.parent_id.id,'currency_match':child.currency_id==root.currency_id,'count_delta':scoped['res.company'].search_count([])-count}))
finally:
    env.cr.rollback();config['test_enable']=previous
    print('BRANCH_REPRO_ROLLBACK_OK')
