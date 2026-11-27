"""Capture original optional follow-up columns with their customers, open items and company contexts."""
from collections import Counter
import hashlib
import json

from odoo.exceptions import AccessError


FIELDS=['followup_responsible_id','followup_reminder_type','followup_status','followup_next_action_date',
        'followup_line_id','total_due','total_overdue']


def capture(env):
    env.cr.execute("SELECT current_date")
    day=str(env.cr.fetchone()[0])
    users=env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1)],order='id')
    result={}
    for actor in users:
        companies=sorted(actor.company_ids.ids)
        for scope in [companies,*([company] for company in companies if len(companies)>1)]:
            key=str(actor.id)+'/'+','.join(map(str,scope))
            partner=env['res.partner'].with_user(actor).with_context(allowed_company_ids=scope,lang='en_US')
            try:
                with env.cr.savepoint():
                    rows=partner.search([],order='id').read(FIELDS,load=None)
                    values=json.loads(json.dumps(rows,sort_keys=True,default=str))
                    raw=json.dumps(values,sort_keys=True).encode()
                    result[key]=dict(records=len(rows),sha256=hashlib.sha256(raw).hexdigest(),
                        nonempty={field:sum(bool(row[field]) for row in rows) for field in FIELDS},
                        status=dict(Counter(str(row['followup_status']) for row in rows)),values=values)
            except AccessError:
                result[key]=dict(denied=True)
    env.cr.rollback()
    return dict(date=day,contexts=result)
