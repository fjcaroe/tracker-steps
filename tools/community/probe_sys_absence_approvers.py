"""Exercise the real manager menu and paid day relations, then approve two new requests in rolled-back future drafts."""
from calendar import monthrange
from datetime import date
from decimal import Decimal
import hashlib
import json

from lxml import etree


TARGET = "COMMUNITY_SYS_PREVIRED_COHORT_20261127U47C"


def checkpoint(env):
    env.cr.rollback()
    env.invalidate_all(flush=False)


def manager(env, uid, company):
    scope = env(user=uid, su=False, context={"allowed_company_ids":[company],"lang":"es_CL",
        "tracking_disable":True,"mail_create_nosubscribe":True,"mail_notify_force_send":False})
    assert not scope.su and scope.company.id==company and scope.user.has_group("hr_holidays.group_hr_holidays_manager")
    return scope


def forms(env):
    env.cr.execute("SELECT DISTINCT company_id FROM hr_leave ORDER BY company_id")
    companies=[row[0] for row in env.cr.fetchall()]
    forms=[]
    for uid in (2,6):
        actor=env["res.users"].browse(uid)
        assert actor.active and not actor.share
        for company in companies:
            assert company in actor.company_ids.ids
            scope=manager(env,uid,company)
            menu=scope.ref("hr_holidays.menu_open_department_leave_approve")
            action=scope.ref("hr_holidays.hr_leave_action_action_approve_department")
            assert menu.id in scope["ir.ui.menu"]._visible_menu_ids() and menu.action==action
            result=scope["ir.actions.actions"]._for_xml_id("hr_holidays.hr_leave_action_action_approve_department")
            assert result["res_model"]=="hr.leave" and result["id"]==action.id
            model=scope["hr.leave"]
            view=next((vid for vid,kind in result["views"] if kind=="form"),False)
            form=model.get_view(view_id=view or False,view_type="form")
            arch=etree.fromstring(form["arch"].encode())
            buttons={b.get("name") for b in arch.xpath("//button[@type='object']")}
            assert {"action_approve","action_validate","action_refuse"}<=buttons
            rows=model.search([("company_id","=",company)])
            assert rows and set(rows.mapped("company_id").ids)=={company}
            rows.read(["state","request_date_from","request_date_to","holiday_status_id"])
            for field in ("employee_id","holiday_status_id","request_date_from"):
                assert arch.xpath("//field[@name=$name]",name=field)
            forms.append([uid,company,menu.id,action.id,form["id"],len(rows)])
    return forms


def pick(env,mode):
    env.cr.execute("""SELECT h.holiday_status_id,w.employee_id,w.contract_id,w.company_id,w.date_start::date,
              w.work_entry_type_id FROM hr_work_entry w JOIN hr_contract c ON c.id=w.contract_id
       JOIN LATERAL (SELECT DISTINCT l.holiday_status_id FROM hr_leave l JOIN hr_leave_type lt ON lt.id=l.holiday_status_id
          WHERE l.employee_id=w.employee_id AND l.state='validate' AND lt.leave_validation_type=%s AND lt.active
          AND lt.requires_allocation='no' AND lt.work_entry_type_id IS NOT NULL AND lt.work_entry_type_id<>w.work_entry_type_id
          ORDER BY l.holiday_status_id LIMIT 1) h ON true
       WHERE w.active AND w.state='draft' AND w.leave_id IS NULL AND c.state='open'
       AND w.date_start>='2026-12-01' AND w.date_start<'2026-12-05' AND w.date_start::date=w.date_stop::date
       AND NOT EXISTS(SELECT 1 FROM hr_leave l WHERE l.employee_id=w.employee_id AND l.state IN ('confirm','validate1','validate')
          AND l.request_date_from<=w.date_start::date AND l.request_date_to>=w.date_start::date)
       AND NOT EXISTS(SELECT 1 FROM hr_payslip p WHERE p.employee_id=w.employee_id AND p.contract_id=w.contract_id
          AND p.state IN ('done','paid') AND p.date_to>=date '2026-12-01')
       AND EXISTS(SELECT 1 FROM hr_payslip p WHERE p.employee_id=w.employee_id AND p.contract_id=w.contract_id
          AND p.struct_id=4 AND p.state IN ('done','paid'))
       ORDER BY w.company_id,w.employee_id,w.date_start LIMIT 1""",(mode,))
    row=env.cr.fetchone()
    if not row:
        raise ValueError("No authentic employee, contract and previously used type with an unprocessed future day")
    return row


def approve(env,mode):
    kind,employee,contract,company,day,regular_type=pick(env,mode)
    first,second=manager(env,2,company),manager(env,6,company)
    leave_type=first["hr.leave.type"].browse(kind)
    leave_type.check_access("read")
    payable=leave_type.work_entry_type_id
    assert payable and payable.id!=regular_type
    c=first["hr.contract"].browse(contract)
    first_ids=first["hr.work.entry"].search([("employee_id","=",employee),("contract_id","=",contract),
        ("leave_id","=",False),("date_start",">=",day),("date_start","<",date(day.year,day.month,day.day+1))]).ids
    assert first_ids
    month_start=day.replace(day=1)
    month_end=day.replace(day=monthrange(day.year,day.month)[1])
    before=c.get_work_hours(month_start,month_end)
    request=first['hr.leave'].create({"name":"Control local de ausencia","employee_id":employee,"holiday_status_id":kind,
                                       "request_date_from":day,"request_date_to":day})
    assert request.state=="confirm" and request.validation_type==mode and request.number_of_days>0
    request.action_approve()
    state_after_first=request.state
    if mode=="both":
        assert state_after_first=="validate1"
        second["hr.leave"].browse(request.id).action_validate()
    request.invalidate_recordset()
    assert request.state=="validate"
    env.flush_all()
    entries=first["hr.work.entry"].search([("leave_id","=",request.id),("contract_id","=",contract),("active","=",True)])
    assert entries and entries.mapped("work_entry_type_id")==payable and set(entries.mapped("company_id").ids)=={company}
    assert all(r.employee_id.id==employee for r in entries)
    after=c.get_work_hours(month_start,month_end)
    # Payroll uses conflict-free work entries. Confirm the current generated state before computing the new draft.
    testslip=first["hr.payslip"].create({"name":"Control local de días de ausencia","employee_id":employee,"contract_id":contract,
        "company_id":company,"date_from":month_start,"date_to":month_end,"struct_id":4})
    rows=testslip._get_worked_day_lines()
    matching=[r for r in rows if r.get("work_entry_type_id")==payable.id]
    assert len(matching)==1
    row=matching[0]
    normal=testslip.get_worked_day_lines(c,month_start,month_end)
    native_typed=sum(r.get("work_entry_type_id")==payable.id for r in normal)
    original=Decimal(str(before.get(payable.id,0)))
    total=Decimal(str(after.get(payable.id,0)))
    delta=total-original
    if delta<=0 or abs(Decimal(str(row["number_of_hours"]))-total)>Decimal("0.0001"):
        raise ValueError("Approved leave hours did not reach the computed payroll day under its original type")
    assert row["code"]==payable.code and row["number_of_days"]>0 and testslip.state in ("draft","verify") and not testslip.move_id
    return {"approval":mode,"first_state":state_after_first,"final_state":request.state,"actors":[2,6] if mode=="both" else [2],
            "matched_original_type":True,"future_work_entries":len(entries),"entered_hours":str(delta),
            "payslip_hours_equal_entry_hours":True,"payslip_day_code_matches_type":True,"normal_form_typed_absence_rows":native_typed,"source_work_entries_setting":bool(testslip.struct_id.use_work_entries)}


def run(env):
    assert env.cr.dbname==TARGET
    result={}
    try:
        checkpoint(env)
        env.cr.execute("SET TRANSACTION READ ONLY")
        result["approver_forms"]=forms(env)
        for mode in ("hr","both"):
            checkpoint(env)
            result[mode]=approve(env,mode)
        return result
    finally:
        checkpoint(env)
