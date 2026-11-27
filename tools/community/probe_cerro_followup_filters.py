"""Record the account user's native contact search capabilities and exact result sets."""
import hashlib
import json

from odoo import api
from probe_cerro_contact_followup import FIELDS


def signature(rows):
    return dict(count=len(rows),sha256=hashlib.sha256(json.dumps(rows.ids).encode()).hexdigest())


def _one(env,scopes):
    actor=env['res.users'].browse(6)
    result={}
    for scope in scopes:
        model=env['res.partner'].with_user(actor).with_context(allowed_company_ids=scope,lang='en_US')
        desc=model.fields_get(FIELDS,attributes=['searchable','sortable','groupable'])
        rows={}
        tests={'followup_status': [('=','in_need_of_action'),('=','with_overdue_invoices'),('=','no_action_needed'),
                                   ('!=','no_action_needed'),('in',['with_overdue_invoices','in_need_of_action']),
                                   ('not in',['in_need_of_action']),('=',False)],
               'followup_line_id':[('=',1),('=',False),('!=',False),('in',[1,2]),('not in',[1,2])],
               'total_due':[('>',0),('<',0),('=',0)],'total_overdue':[('>',0),('<',0),('=',0)]}
        for name,cases in tests.items():
            if desc[name].get('searchable'):
                for operator,value in cases:
                    try:
                        with env.cr.savepoint():
                            found=model.search([(name,operator,value)],order='id')
                            rows[name+' '+operator+' '+str(value)]=signature(found)
                    except (NotImplementedError,ValueError) as error:
                        rows[name+' '+operator+' '+str(value)]={'rejected':type(error).__name__}
        result[','.join(map(str,scope))]=dict(descriptions=desc,rows=rows)
    env.cr.rollback()
    return result


def capture(env):
    result={}
    for scope in ([1],[2],[2,31],[31]):
        with env.registry.cursor() as cr:
            fresh=api.Environment(cr,env.uid,dict(env.context))
            result.update(_one(fresh,[scope]))
            cr.rollback()
    return result
