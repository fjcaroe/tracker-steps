"""Characterize the original negative-net button on the isolated SyS reference using ordinary operators."""
import json
import hashlib
from odoo import fields
from collections import Counter
from decimal import Decimal

from odoo.exceptions import UserError


NATIVE = "MANAGEMENT_QA_SYS_PREVIRED_20261126U40N"


def characterize(env):
    assert env.cr.dbname == NATIVE
    env.cr.rollback()
    env.cr.execute("SET TRANSACTION READ ONLY")
    env.cr.execute("SELECT id,company_id FROM hr_payslip WHERE has_negative_net_to_report ORDER BY id")
    flagged = env.cr.fetchall()
    assert len(flagged) == 3
    results = []
    try:
        for uid in (2, 6):
            for slip_id, company in flagged:
                scope = env(user=uid, su=False, context={"lang":"es_CL", "allowed_company_ids":[company],
                                                         "tracking_disable":True, "mail_notify_force_send":False})
                slip = scope["hr.payslip"].browse(slip_id)
                slip.check_access("read")
                assert not scope.su and scope.company == slip.company_id
                state = {"actor": uid, "source": slip.id, "state": slip.state, "flag": bool(slip.has_negative_net_to_report),
                         "visible": bool(slip.negative_net_to_report_display), "nonzero": bool(slip.negative_net_to_report_amount)}
                try:
                    with env.cr.savepoint():
                        action = slip.action_report_negative_amount()
                        env.flush_all()
                        state["return"] = {k: action[k] for k in ("type", "res_model", "target", "view_mode") if k in action} if isinstance(action, dict) else type(action).__name__
                except Exception as exc:
                    if getattr(exc, "pgcode", None) == "25006":
                        state["operation"] = "attempted_write"
                    elif isinstance(exc, UserError):
                        state["operation"] = type(exc).__name__
                    else:
                        raise
                results.append(state)
        return results
    finally:
        env.cr.rollback()
from dateutil.relativedelta import relativedelta


def transaction_counters(env):
    env.cr.execute("SELECT relname,n_tup_ins,n_tup_upd,n_tup_del FROM pg_stat_xact_user_tables WHERE schemaname='public'")
    return {key:(i,u,d) for key,i,u,d in env.cr.fetchall()}


def domain_snapshot(env, emp):
    env.cr.execute("SELECT id,has_negative_net_to_report FROM hr_payslip WHERE employee_id=%s", (emp,))
    flags = dict(env.cr.fetchall())
    env.cr.execute("""SELECT i.id,i.payslip_id,i.amount,t.code FROM hr_payslip_input i
                   JOIN hr_payslip p ON p.id=i.payslip_id LEFT JOIN hr_payslip_input_type t ON t.id=i.input_type_id
                   WHERE p.employee_id=%s""", (emp,))
    inputs = {k:(p,a,c) for k,p,a,c in env.cr.fetchall()}
    env.cr.execute("""SELECT a.id,a.res_id,a.activity_type_id FROM mail_activity a
                      JOIN hr_payslip p ON p.id=a.res_id WHERE a.res_model='hr.payslip' AND p.employee_id=%s""", (emp,))
    return flags, inputs, {k:(p,t) for k,p,t in env.cr.fetchall()}


def rule_digest(cr, slip):
    cr.execute("""SELECT salary_rule_id,code,amount,quantity,rate,total FROM hr_payslip_line
                  WHERE slip_id=%s ORDER BY salary_rule_id,id""",(slip,))
    rows = [[rule,code,*[format(Decimal(str(v)).normalize(),"f") if v is not None else None for v in values]]
            for rule,code,*values in cr.fetchall()]
    return len(rows),hashlib.sha256(json.dumps(rows,separators=(",",":")).encode()).hexdigest()


def original_rows(env):
    tables = ("hr_payslip","hr_payslip_input","hr_payslip_line","hr_payslip_worked_days","hr_leave",
              "account_move","account_move_line","mail_activity","mail_message","res_users","res_groups_users_rel")
    result = {}
    for table in tables:
        env.cr.execute("SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) "
                       "FROM (SELECT md5(to_jsonb(t)::text) h FROM " + table + " t) as src")
        result[table] = env.cr.fetchone()
    return result


def effects(env, verify_first=False):
    native = env.cr.dbname == "MANAGEMENT_QA_SYS_REPORT_ROLES_20261126U40RP"
    assert native or env.cr.dbname in ("COMMUNITY_SYS_PREVIRED_COHORT_20261127U49D", "COMMUNITY_SYS_PREVIRED_COHORT_20261127U49E",
                                       "COMMUNITY_SYS_PREVIRED_COHORT_20261127U49F")
    env.cr.rollback()
    cr = env.cr
    cr.execute("SELECT id,company_id FROM hr_payslip WHERE has_negative_net_to_report ORDER BY id")
    flagged = cr.fetchall()
    assert len(flagged) == 3
    cr.execute("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public'")
    counters = dict(cr.fetchall())
    initial_rows = original_rows(env)
    result = []
    for uid in (2, 6):
        for original_id, company in flagged:
            cr.rollback(); env.invalidate_all(flush=False)
            try:
                scope = env(user=uid,su=False,context={"lang":"es_CL","allowed_company_ids":[company],
                             "tracking_disable":True, "mail_notify_force_send":False, "mail_create_nosubscribe":True})
                s = scope["hr.payslip"].browse(original_id)
                s.check_access("read")
                day = s.date_to + relativedelta(days=1)
                if native:
                    p = scope["hr.payslip"].create({"name":"Ensayo local de arrastre de neto","employee_id":s.employee_id.id,
                                           "company_id":company,"contract_id":s.contract_id.id,"struct_id":s.struct_id.id,
                                           "date_from":day,"date_to":day+relativedelta(months=1,days=-1)})
                else:
                    from odoo.tests import Form
                    card = Form(scope["hr.payslip"])
                    card.date_from, card.date_to = day, day+relativedelta(months=1,days=-1)
                    card.employee_id = s.employee_id
                    if card.contract_id != s.contract_id:
                        card.contract_id = s.contract_id
                    if card.struct_id != s.struct_id:
                        card.struct_id = s.struct_id
                    p = card.save()
                assert not scope.su and p.id != s.id and p.state == "draft" and p.negative_net_to_report_display
                activity_domain=[("res_model","=","hr.payslip"),("res_id","=",p.id),
                                 ("activity_type_id","=",scope.ref("hr_payroll.mail_activity_data_hr_payslip_negative_net").id)]
                activity_model=scope["mail.activity"]
                pre={}
                if verify_first:
                    pre["before_compute"]=activity_model.search_count(activity_domain)
                    p.compute_sheet()
                    env.flush_all()
                    pre["after_compute_before_read"]=activity_model.search_count(activity_domain)
                    assert p.state=="verify" and p.negative_net_to_report_display
                    p.invalidate_recordset(["negative_net_to_report_display"])
                    assert p.negative_net_to_report_display
                    acts=activity_model.search(activity_domain)
                    pre["after_two_reads"]=len(acts)
                    pre["assigned_to_contract_officer"]=all(a.user_id==p.contract_id.hr_responsible_id for a in acts)
                    pre["has_summary_and_note"]=all(bool(a.summary and a.note) for a in acts)
                    pre["due_on_today"]=all(a.date_deadline==fields.Date.context_today(p) for a in acts)
                expected = p.negative_net_to_report_amount
                assert expected
                env.flush_all()
                first = domain_snapshot(env,s.employee_id.id)
                query_messages="SELECT count(*) FROM mail_message WHERE model='hr.payslip' AND res_id=%s"
                cr.execute(query_messages,(p.id,))
                before_messages,=cr.fetchone()
                cr.execute("SELECT id,to_jsonb(l) FROM hr_leave l WHERE employee_id=%s",(s.employee_id.id,))
                prior_leaves = dict(cr.fetchall())
                prior_flags = scope["hr.payslip"].browse([k for k,v in first[0].items() if v])
                previous_net = sum(Decimal(str(v)) for v in prior_flags.mapped("net_wage"))
                stats = transaction_counters(env)
                action = p.with_context(tracking_disable=False).action_report_negative_amount()
                env.flush_all()
                last = domain_snapshot(env,s.employee_id.id)
                final_stats = transaction_counters(env)
                changes={table:[b-a for a,b in zip(old,final_stats[table])] for table,old in stats.items() if old!=final_stats[table]}
                cr.execute(query_messages,(p.id,))
                new_messages=cr.fetchone()[0]-before_messages
                before_flags, before_inputs, before_activities = first
                after_flags, after_inputs, after_activities = last
                affected_flags = [k for k in before_flags if before_flags[k] != after_flags[k]]
                created = [value for k,value in after_inputs.items() if k not in before_inputs]
                cr.execute("SELECT id,to_jsonb(l) FROM hr_leave l WHERE employee_id=%s",(s.employee_id.id,))
                leave_updates = Counter()
                for key, current in cr.fetchall():
                    old = prior_leaves[key]
                    for field in old:
                        if old[field] != current[field]:
                            values = (old[field], current[field]) if field in ("state", "payslip_state") else ("","")
                            leave_updates[(field,*values)] += 1
                result.append({"actor":uid,"source":original_id,"changes":changes,"before_action":pre,"messages_added_to_slip":new_messages,
                    "flags":[(bool(before_flags[k]),bool(after_flags[k])) for k in affected_flags],
                    "rules":rule_digest(cr,p.id),"worked_types":sorted(p.worked_days_line_ids.mapped("work_entry_type_id").ids),
                    "input_uses_type_name":all(r.name==r.input_type_id.name for r in p.input_line_ids),
                    "input_name_present":all(bool(r.name) for r in p.input_line_ids),
                    "created_inputs":[{"in_draft":slip==p.id,"code":code,"matches_report_amount":amount==expected,
                                       "positive":amount>0,"matches_abs_report_amount":amount==abs(expected),
                                       "matches_negated_report_amount":amount==-expected} for slip,amount,code in created],
                    "earlier_input_edits":sum(k not in after_inputs or v!=after_inputs[k] for k,v in before_inputs.items()),
                    "previous_net_matches_display":previous_net==Decimal(str(expected)),
                    "cleared_all_employee_flags":set(affected_flags)==set(prior_flags.ids),
                    "flagged_periods_starting_on_or_after_draft":len(prior_flags.filtered(lambda old:old.date_from>=p.date_from)),
                    "leave_changes":[[*k,v] for k,v in sorted(leave_updates.items())],
                    "visible_after":bool(p.negative_net_to_report_display),"state_after":p.state,"journal_entry_created":bool(p.move_id),
                    "new_type_from_existing_master":all(code for _,_,code in created),
                    "activities_created":len(after_activities.keys()-before_activities.keys()),
                    "activities_removed":len(before_activities.keys()-after_activities.keys()),
                    "return":{k:action[k] for k in ("type","res_model","target","view_mode") if k in action} if isinstance(action,dict) else type(action).__name__})
                if not native:
                    repeat = domain_snapshot(env,s.employee_id.id)
                    p.action_report_negative_amount()
                    env.flush_all()
                    assert repeat == domain_snapshot(env,s.employee_id.id)
            finally:
                cr.rollback()
                env.invalidate_all(flush=False)
    cr.execute("SELECT sequencename,last_value FROM pg_sequences WHERE schemaname='public'")
    final_counters = dict(cr.fetchall())
    assert counters.keys()==final_counters.keys() and initial_rows==original_rows(env)
    advanced={k:[counters[k],final_counters[k]] for k in counters if counters[k]!=final_counters[k]}
    cr.rollback()
    return {"cases":result,"advanced_sequences":advanced,"original_tables":list(initial_rows),
            "same_original_rows":True,"backup":"acfa47a2642725b22d92a0f53c40ccafc2c43205097db87dacbc987f6071de2b"}
