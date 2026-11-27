"""Run on U48 only, after the leave-approval fixture from probe_sys_absence_approvers has been loaded."""
from odoo.tests import Form
from odoo.exceptions import AccessError
from lxml import etree


def menus(scope):
    payslips = scope["hr.payslip"]
    for key, action_name, number in (("menu_hr_payroll_employee_payslips", "action_view_hr_payslip_month_form", 1420),
                                     ("menu_hr_payroll_employee_payslips_to_pay", "hr_payslip_action_view_to_pay", 1418)):
        menu = scope.ref("hr_payroll." + key)
        assert menu.id in scope["ir.ui.menu"]._visible_menu_ids() and menu.action.id == number
        action = scope["ir.actions.actions"]._for_xml_id("hr_payroll." + action_name)
        assert action["id"] == number and action["res_model"] == payslips._name
        views = dict((kind, vid) for vid, kind in action["views"])
        listing = payslips.get_view(view_id=views["list"], view_type="list")
        arch = etree.fromstring(listing["arch"].encode())
        fields = {n.get("name"): {} for n in arch.xpath("./field[@name]")}
        assert fields.keys() <= payslips._fields.keys(), sorted(fields.keys() - payslips._fields.keys())
        page = payslips.web_search_read([("company_id", "=", scope.company.id)], fields, limit=1)
        assert page["records"]
        view = payslips.get_view(view_id=views["form"], view_type="form")
        assert view["id"] == scope.ref("hr_payroll.view_hr_payslip_form").id == 5018
    return 2


def histories(env):
    env.cr.execute("SELECT DISTINCT company_id FROM hr_payslip ORDER BY company_id")
    companies = [c for c, in env.cr.fetchall()]
    result = {}
    for uid in (2, 6):
        counts = dict(companies=0, denied_companies=0, menus=0, slips=0, warnings=0, negative_flags=0, accounting_links=0,
                      opened_moves=0, rendered_report_actions=0, opened_work_entries=0, pending_activities=0)
        for company in companies:
            if company not in env["res.users"].browse(uid).company_ids.ids:
                assert (uid, company) == (6, 35)
                try:
                    manager(env, uid, company)
                except AccessError:
                    counts["denied_companies"] += 1
                    continue
                raise AssertionError("Original company exclusion was not enforced")
            scope = manager(env, uid, company)
            counts["companies"] += 1
            counts["menus"] += menus(scope)
            slips = scope["hr.payslip"].search([("company_id", "=", company)])
            fields = ["has_negative_net_to_report", "sum_worked_hours", "warning_message", "paid_date", "move_id"]
            rows = slips.read(fields)
            counts["slips"] += len(rows)
            counts["warnings"] += sum(bool(r["warning_message"]) for r in rows)
            counts["negative_flags"] += sum(bool(r["has_negative_net_to_report"]) for r in rows)
            counts["accounting_links"] += sum(bool(r["move_id"]) for r in rows)
            env.cr.execute("SELECT id FROM hr_payslip WHERE company_id=%s AND state IN ('done','paid') "
                           "ORDER BY (move_id IS NOT NULL) DESC,id LIMIT 1", (company,))
            found = env.cr.fetchone()
            if found:
                slip = scope["hr.payslip"].browse(found[0])
                card = Form(slip)
                assert card.employee_id == slip.employee_id and card.state == slip.state
                assert card.sum_worked_hours == slip.sum_worked_hours and len(card.line_ids) == len(slip.line_ids)
                if slip.move_id:
                    linked = slip.action_open_move()
                    assert linked["res_model"] == "account.move" and linked["res_id"] == slip.move_id.id
                    scope["account.move"].browse(linked["res_id"]).read(["state"])
                    counts["opened_moves"] += 1
                original = scope.ref("hr_payroll.action_report_payslip")
                report = slip.action_print_payslip()
                assert original.id == 1431 and report["report_name"] == original.report_name
                counts["rendered_report_actions"] += 1
                action = slip.action_open_work_entries()
                scope[action["res_model"]].search(action["domain"], limit=1).read(["work_entry_type_id"])
                counts["opened_work_entries"] += 1
                for method, field in ((slip.action_open_attendances, "attendance_count"), (slip.action_open_expenses, "expenses_count")):
                    related = method()
                    assert scope[related["res_model"]].search_count(related["domain"]) == slip[field]
            negative = slips.filtered("negative_net_to_report_display")
            for slip in negative:
                action = slip.action_sys_open_negative_activities()
                counts["pending_activities"] += scope[action["res_model"]].search_count(action["domain"])
        expected = (765, 90, 3, 702) if uid == 2 else (763, 88, 3, 702)
        assert (counts["slips"], counts["warnings"], counts["negative_flags"], counts["accounting_links"]) == expected
        result[uid] = counts
    return result


def new_form(env, mode, uid):
    before = approve(env, mode)
    assert before["normal_form_typed_absence_rows"] == 1
    env.cr.execute("SELECT id,company_id FROM hr_payslip WHERE name='Control local de días de ausencia' ORDER BY id DESC LIMIT 1")
    test, company = env.cr.fetchone()
    scope = manager(env, uid, company)
    model = scope["hr.payslip"]
    original = model.browse(test)
    menus(scope)
    form = Form(model)
    form.date_from = original.date_from
    form.date_to = original.date_to
    form.employee_id = original.employee_id
    assert form.contract_id == original.contract_id and form.struct_id == original.struct_id
    assert len(form.worked_days_line_ids) == len(original._get_worked_day_lines()) > 0
    assert not len(form.input_line_ids)
    kind = scope["hr.payslip.input.type"].search([("code", "=", "DEDUCTION")], limit=1)
    with form.input_line_ids.new() as row:
        row.input_type_id = kind
        row.amount = 1
    form.date_from = original.date_from
    assert len(form.input_line_ids) == 1
    slip = form.save()
    assert slip.state == "draft" and not slip.move_id and slip.contract_id == original.contract_id
    expected = {r["work_entry_type_id"]: (r["number_of_days"], r["number_of_hours"]) for r in original._get_worked_day_lines()}
    actual = {r.work_entry_type_id.id: (r.number_of_days, r.number_of_hours) for r in slip.worked_days_line_ids}
    assert expected == actual and slip.sum_worked_hours == sum(row[1] for row in actual.values())
    assert slip.input_line_ids.input_type_id == kind and slip.input_line_ids.code == kind.code
    reopened = Form(slip)
    assert reopened.employee_id == original.employee_id and len(reopened.input_line_ids) == 1
    assert len(reopened.worked_days_line_ids) == len(actual)
    return {"approval": mode, "actor": uid, "hours_from_new_leave": before["entered_hours"], "day_types": len(actual),
            "typed_input_reopened": True, "state": slip.state, "confirmed_journal_entry": bool(slip.move_id)}


def operator_forms(env):
    assert env.cr.dbname in ("COMMUNITY_SYS_PREVIRED_COHORT_20261127U48C", "COMMUNITY_SYS_PREVIRED_COHORT_20261127U48D")
    try:
        checkpoint(env)
        env.cr.execute("SET TRANSACTION READ ONLY")
        historical = histories(env)
        fields = []
        for model, field in (("hr.payslip", "sum_worked_hours"), ("hr.payslip", "warning_message"),
                             ("hr.payslip", "has_negative_net_to_report"), ("hr.payslip", "paid_date"),
                             ("hr.payslip.worked_days", "ytd"), ("hr.expense.sheet", "payslip_id")):
            original = env["ir.model.fields"].search([("model", "=", model), ("name", "=", field)])
            assert len(original) == 1 and original.store
            fields.append(original.id)
        results = []
        for mode, uid in (("hr", 2), ("both", 6)):
            checkpoint(env)
            results.append(new_form(env, mode, uid))
        return {"historical": historical, "future_drafts": results, "stored_field_ids": fields}
    finally:
        checkpoint(env)


def october_forms(env, references):
    from probe_sys_october_drafts import amounts, digest, protect_existing
    assert env.cr.dbname in ("COMMUNITY_SYS_PREVIRED_COHORT_20261127U48C", "COMMUNITY_SYS_PREVIRED_COHORT_20261127U48D")
    results = []
    try:
        for uid in (2, 6):
            for original_id, expected in references:
                checkpoint(env)
                protect_existing(env.cr, "hr_payslip", (("hr_payslip", "id"), ("hr_payslip_line", "slip_id"),
                                 ("hr_payslip_input", "payslip_id"), ("hr_payslip_worked_days", "payslip_id")))
                protect_existing(env.cr, "account_move", (("account_move", "id"), ("account_move_line", "move_id")))
                scope = manager(env, uid, 37)
                original = scope["hr.payslip"].browse(original_id)
                menus(scope)
                card = Form(scope["hr.payslip"])
                card.date_from, card.date_to = original.date_from, original.date_to
                card.employee_id = original.employee_id
                if card.contract_id != original.contract_id:
                    card.contract_id = original.contract_id
                slip = card.save()
                slip.compute_sheet()
                env.flush_all()
                calculated = digest(amounts(env.cr, slip.id))
                assert calculated == expected and slip.state == "verify" and not slip.move_id
                slip.with_context(payslip_generate_pdf=True).action_payslip_done()
                env.flush_all()
                assert slip.state == "done" and slip.move_id and slip.move_id != original.move_id
                assert calculated == digest(amounts(env.cr, slip.id))
                assert slip.action_open_move()["res_id"] == slip.move_id.id
                report = scope.ref("hr_payroll.action_report_payslip")
                assert slip.action_print_payslip()["report_name"] == report.report_name
                html, _format = report._render_qweb_html(report.report_name, slip.ids)
                printed = {int(n.get("data-step-line-id")) for n in etree.HTML(html).xpath("//*[@data-step-line-id]")}
                assert printed and printed <= set(slip.line_ids.ids)
                results.append({"uid": uid, "day_types": len(slip.worked_days_line_ids), "lines": len(slip.line_ids),
                                "verified": True, "confirmed": True, "report_action": 1431, "printable_lines": len(printed)})
        return results
    finally:
        checkpoint(env)
