"""Exercise receivable cutoffs on disposable accounting lines while preserving every original posting."""
from datetime import timedelta
import json

from probe_cerro_contact_followup import FIELDS


def descriptors(env):
    models={
        'res.partner':FIELDS,
        'account_followup.followup.line':['name','delay','company_id'],
        'account.move.line':['followup_line_id'],
    }
    result={}
    for model,names in models.items():
        result[model]={}
        for name in names:
            f=env[model]._fields[name]
            result[model][name]={key:getattr(f,key,None) for key in ('type','comodel_name','currency_field',
                'company_dependent','readonly','store','required','copy','groups','index','ondelete','string','help')}
            result[model][name]['choices']=f._description_selection(env) if f.type=='selection' else []
            result[model][name]['related']=f.related or False
    env.cr.rollback()
    return result


def reference(env):
    return dict(fields=descriptors(env),data=capture(env))


def capture(env):
    return _capture(env, False)


def combinations(env):
    return _capture(env, True)


def changes(env):
    return _capture(env, 'changes')


def _capture(env, mixed):
    database=env.cr.dbname
    assert database=='MANAGEMENT_QA_CERRO_BOM_20261126U42N' or database.startswith('COMMUNITY_CERRO_BOM_PACKING_20261127U46')
    user=env['res.users'].browse(6)
    partner=env['res.partner'].with_user(user).with_context(allowed_company_ids=[1],lang='en_US',tracking_disable=True)
    contact=partner.create({'name':'QA isolated follow-up dates','company_id':1})
    env.flush_all()
    cr=env.cr
    cr.execute("SELECT current_date")
    today=cr.fetchone()[0]
    cr.execute("""SELECT l.id FROM account_move_line l JOIN account_account a ON a.id=l.account_id
                  WHERE l.company_id=1 AND a.account_type='asset_receivable' AND l.parent_state='posted'
                    AND l.partner_id IS NOT NULL AND l.amount_residual>0 ORDER BY l.id LIMIT 1""")
    original=cr.fetchone()[0]
    cr.execute("SELECT id,delay FROM account_followup_followup_line WHERE company_id=1 ORDER BY delay,id")
    levels=cr.fetchall()
    assert [row[1] for row in levels]==[15,30]
    def snapshot(label,days,amount=100,level=None,next_days=None,manual=False,without_due=False,reconciled=False,second=None,child=False):
        cr.execute("DELETE FROM account_move_line WHERE id IN (-460401,-460402)")
        maturity=today+timedelta(days=days)
        due=None if without_due else str(maturity)
        values=dict(id=-460401,partner_id=contact.id,date=str(maturity),date_maturity=due,
                    debit=max(0,amount),credit=max(0,-amount),balance=amount,amount_currency=amount,amount_residual=amount,
                    amount_residual_currency=amount,followup_line_id=level,reconciled=reconciled)
        cr.execute("""INSERT INTO account_move_line
                      SELECT (jsonb_populate_record(NULL::account_move_line,to_jsonb(template)||%s::jsonb)).*
                      FROM account_move_line template WHERE template.id=%s""",(json.dumps(values),original))
        if second:
            other=dict(values)
            day2,amount2,level2=second
            other.update(id=-460402,date=str(today+timedelta(days=day2)),date_maturity=str(today+timedelta(days=day2)),
                         debit=max(0,amount2),credit=max(0,-amount2),balance=amount2,amount_currency=amount2,
                         amount_residual=amount2,amount_residual_currency=amount2,followup_line_id=level2)
            if child:
                other['partner_id']=child_partner.id
            cr.execute("""INSERT INTO account_move_line
                          SELECT (jsonb_populate_record(NULL::account_move_line,to_jsonb(template)||%s::jsonb)).*
                          FROM account_move_line template WHERE template.id=%s""",(json.dumps(other),original))
        cr.execute("""UPDATE res_partner SET followup_reminder_type=%s,followup_next_action_date=%s::jsonb WHERE id=%s""",
                   ('manual' if manual else 'automatic',json.dumps({'1':str(today+timedelta(days=next_days))}) if next_days is not None else None,contact.id))
        env.invalidate_all(flush=False)
        row=contact.read(FIELDS,load=None)[0]
        del row['id']
        return label,{k:str(v) if k=='followup_next_action_date' and v else v for k,v in row.items()}
    scenarios=[snapshot('future',1),snapshot('today',0),snapshot('yesterday',-1),snapshot('fourteen',-14),
               snapshot('first_cutoff',-15),snapshot('sixteen',-16),snapshot('second_cutoff',-30),snapshot('thirty_one',-31),
               snapshot('credit',-45,-100),snapshot('null_maturity',-16,without_due=True),
               snapshot('remind_tomorrow',-60,next_days=1),snapshot('remind_today',-60,next_days=0),
               snapshot('manual',-60,manual=True),snapshot('already_first',-16,level=levels[0][0]),
               snapshot('already_first_long',-45,level=levels[0][0]),snapshot('already_last',-60,level=levels[1][0]),
               snapshot('zero',-60,0),snapshot('reconciled',-60,0,reconciled=True)]
    if mixed is True:
        child_partner=partner.create({'name':'QA child follow-up','parent_id':contact.id})
        env.flush_all()
        first,last=levels[0][0],levels[-1][0]
        scenarios=[snapshot('prior_first_ten',-10,level=first),snapshot('prior_last_ten',-10,level=last),
                   snapshot('prior_last_fifteen',-15,level=last),snapshot('prior_last_twenty',-20,level=last),
                   snapshot('prior_last_thirty',-30,level=last),snapshot('prior_zero_future',2,level=first),
                   snapshot('zero_plus_credit',-35,100,second=(-35,-100,None)),
                   snapshot('net_credit',-35,100,second=(-35,-125,None)),
                   snapshot('credit_young',-40,100,second=(1,-125,None)),
                   snapshot('mixed_positive',-35,150,second=(-3,-30,None)),
                   snapshot('old_credit_new_debit',-40,-80,second=(-1,100,None)),
                   snapshot('pending_and_prior',-10,100,second=(-3,80,first)),
                   snapshot('pending_and_last',-20,100,second=(-3,80,last)),
                   snapshot('prior_and_credit',-16,100,second=(-60,-10,last)),
                   snapshot('old_child_debit',1,30,second=(-40,60,None),child=True)]
        childrow=child_partner.read(FIELDS,load=None)[0]
        del childrow['id']
        scenarios.append(('child',childrow))
    if mixed=='changes':
        first,last=levels[0][0],levels[-1][0]
        scenarios=[snapshot('first_applied_cutoff',-15,level=first),snapshot('last_applied_after_cutoff',-31,level=last),
                   snapshot('future_debit_old_credit',2,150,second=(-40,-100,None)),
                   snapshot('old_debit_young_credit',-32,60,second=(-2,-80,None))]
        snapshot('background',-40,100,second=(-5,70,None))
        # The level inverse writes through the accounting API, which checks that
        # the posted move still balances. Offset both disposable receivables.
        cr.execute('''INSERT INTO account_move_line SELECT
               (jsonb_populate_record(NULL::account_move_line,to_jsonb(template)||%s::jsonb)).*
               FROM (
                   SELECT line.* FROM account_move_line line JOIN account_account a ON a.id=line.account_id
                   WHERE line.move_id=(SELECT move_id FROM account_move_line WHERE id=%s)
                     AND a.account_type NOT IN ('asset_receivable','liability_payable')
                   ORDER BY line.id LIMIT 1
               ) template''',(json.dumps(dict(id=-460404,partner_id=contact.id,debit=0,credit=170,
                    balance=-170,amount_currency=-170,amount_residual=0,amount_residual_currency=0,
                    reconciled=False,followup_line_id=None)),original))
        assert cr.rowcount==1
        for label,newlevel in [('raise_to_first',first),('raise_to_last',last),('lower_to_first',first),('clear',False)]:
            with cr.savepoint():
                contact.write({'followup_line_id':newlevel})
                env.flush_all()
                cr.execute('SELECT followup_line_id FROM account_move_line WHERE id IN (-460401,-460402) ORDER BY id DESC')
                applied=[r[0] for r in cr.fetchall()]
                env.invalidate_all(flush=False)
                row=contact.read(FIELDS,load=None)[0]
                scenarios.append((label,dict(stage=row['followup_line_id'],applied=applied,status=row['followup_status'],
                    next=str(row['followup_next_action_date']) if row['followup_next_action_date'] else False)))
        cr.execute('DELETE FROM account_move_line WHERE id=-460404')
        contact.write({'company_id':False})
        env.flush_all()
        cr.execute('DELETE FROM account_move_line WHERE id IN (-460401,-460402)')
        for company,amount,line_id in [(1,100,-460401),(2,200,-460402),(31,300,-460403)]:
            cr.execute('SELECT id FROM account_move WHERE company_id=%s AND state=%s ORDER BY id LIMIT 1',(company,'posted'))
            move_id=cr.fetchone()[0]
            parent=2 if company==31 else company
            cr.execute('''SELECT l.id FROM account_move_line l JOIN account_account a ON a.id=l.account_id
                       WHERE l.company_id=%s AND a.account_type='asset_receivable' AND l.parent_state='posted'
                       ORDER BY l.id LIMIT 1''',(parent,))
            src=cr.fetchone()[0]
            date=str(today-timedelta(days=45))
            vals=dict(id=line_id,move_id=move_id,company_id=company,date=date,date_maturity=date,partner_id=contact.id,
                      debit=amount,credit=0,balance=amount,amount_currency=amount,amount_residual=amount,
                      amount_residual_currency=amount,followup_line_id=None,reconciled=False)
            cr.execute('''INSERT INTO account_move_line SELECT
                      (jsonb_populate_record(NULL::account_move_line,to_jsonb(l)||%s::jsonb)).*
                      FROM account_move_line l WHERE l.id=%s''',(json.dumps(vals),src))
        for scope in [[1],[2],[31],[1,2,31],[2,31],[31,2]]:
            env.invalidate_all(flush=False)
            row=contact.with_context(allowed_company_ids=scope).read(FIELDS,load=None)[0]
            del row['id']
            scenarios.append(('company_'+','.join(map(str,scope)),row))
    env.cr.rollback()
    return dict(as_of=str(today),cases=dict(scenarios))
