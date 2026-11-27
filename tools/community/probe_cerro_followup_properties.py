"""Compare genuine company-specific reminder settings saved from a new contact in the private original and Community."""
from datetime import timedelta

from odoo.exceptions import AccessError

from probe_cerro_contact_followup import FIELDS


def exercise(env):
    assert env.cr.dbname=='MANAGEMENT_QA_CERRO_BOM_20261126U42N' or env.cr.dbname.startswith('COMMUNITY_CERRO_BOM_PACKING_20261127U46')
    env.cr.execute('SELECT current_date')
    today=env.cr.fetchone()[0]
    actor=env['res.users'].browse(6)
    one=env['res.partner'].with_user(actor).with_context(allowed_company_ids=[1],lang='en_US',tracking_disable=True)
    pk=one.web_save({'name':'QA account follow-up','company_id':False},specification={'id':{}})[0]['id']
    item=one.browse(pk)
    future=today+timedelta(days=4)
    past=today-timedelta(days=2)
    item.web_save({'followup_responsible_id':actor.id,'followup_next_action_date':str(future),
                   'followup_reminder_type':'manual'},specification={'id':{}})
    two=item.with_context(allowed_company_ids=[2])
    assert two.followup_next_action_date is False and not two.followup_responsible_id
    assert two.followup_reminder_type=='manual'
    two.web_save({'followup_next_action_date':str(past)},specification={'id':{}})
    assert item.followup_next_action_date==future and two.followup_next_action_date==past
    result={}
    for operator in env['res.users'].search([('active','=',True),('share','=',False)]):
        record=env['res.partner'].with_user(operator).with_context(allowed_company_ids=operator.company_ids.ids,lang='en_US').browse(pk)
        try:
            values=record.read(FIELDS,load=None)[0]
            day=values.pop('followup_next_action_date')
            values.pop('id')
            values['relative_date']=(day-today).days if day else False
            result[str(operator.id)]=values
        except AccessError:
            result[str(operator.id)]=dict(denied=True)
    env.flush_all()
    env.cr.execute('SELECT followup_responsible_id,followup_next_action_date,followup_reminder_type FROM res_partner WHERE id=%s',(pk,))
    responsible,next_day,kind=env.cr.fetchone()
    assert responsible=={'1':6} and next_day=={'1':str(future),'2':str(past)} and kind=='manual'
    item.write({'followup_responsible_id':False,'followup_next_action_date':False})
    assert not item.followup_responsible_id and not item.followup_next_action_date and two.followup_next_action_date==past
    env.cr.rollback()
    return dict(operators=result,companies=list(sorted(next_day)),responsible=responsible,reminder=kind)
