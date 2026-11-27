"""Open the affected actions as existing internal users of the restored SyS company."""
from ast import literal_eval
from collections import Counter

from lxml import etree
from odoo.exceptions import AccessError
from odoo.tools.safe_eval import safe_eval


ACTIONS = (
    ("hr_timesheet.act_hr_timesheet_line", "hr_timesheet.timesheet_menu_activity_mine", "timesheet"),
    ("project_sms.project_task_act_window_sms_composer", None, "sms"),
    ("l10n_latam_invoice_document.action_document_type", "l10n_latam_invoice_document.menu_document_type", "documents"),
    ("l10n_cl_simpledigital_payroll.action_hr_libro_remuneraciones_wizard",
     "l10n_cl_simpledigital_payroll.menu_hr_payroll_libro_remuneraciones", "libro"),
    ("step_hr_previred.action_previred_export_wizard", None, "previred"),
    ("step_hr_previred.action_previred_profile", "step_hr_previred_simpledigital.menu_previred_profile", "profile"),
)


def open_action(scope, xmlid, menu, kind):
    model = scope["ir.actions.act_window"]
    action = model._for_xml_id(xmlid)
    res = scope[action["res_model"]]
    res.check_access("read")
    if menu and scope.ref(menu).id not in scope["ir.ui.menu"]._visible_menu_ids():
        return None
    if kind == "sms":
        record = scope["project.task"].search([], limit=1)
        if not record:
            return None
        bindings = scope["ir.actions.actions"].get_bindings("project.task").get("action", [])
        if action["id"] not in {entry["id"] for entry in bindings}:
            return None
        default = safe_eval(action["context"], {"active_ids": record.ids})
        res = res.with_context(active_model="project.task", active_ids=record.ids, **default)
        wizard = res.new(res.default_get(["composition_mode", "res_ids", "res_model", "mass_keep_log"]))
        assert wizard.composition_mode == "mass" and wizard.mass_keep_log
        assert wizard.res_model == "project.task" and literal_eval(wizard.res_ids) == record.ids
    view = res.get_view(view_type="form")
    arch = etree.fromstring(view["arch"].encode("utf8"))
    assert arch.tag == "form" and arch.xpath(".//field")
    result = {"action": action["id"], "model": res._name, "form": view["id"],
              "fields": len(arch.xpath(".//field")), "menu": bool(menu)}
    if kind == "timesheet":
        rows = res.search([("project_id", "!=", False), ("employee_id", "!=", False)], limit=1)
        if rows:
            rows.read(["unit_amount", "date", "project_id", "employee_id"])
        result["accessible_sample"] = len(rows)
    elif kind == "documents":
        original = res.search([("active", "=", True)], limit=1)
        if not original:
            return None
        original.read(["code", "country_id"])
        result["accessible_sample"] = 1
    elif kind == "sms":
        result["prepared_composer"] = True
    return result


def run(shell):
    shell.cr.rollback()
    shell.cr.execute("SET TRANSACTION READ ONLY")
    users = shell["res.users"].sudo().search([("active", "=", True), ("share", "=", False)], order="id")
    users = users.filtered(lambda user: user.id != 1 and user.company_ids)
    assert users
    stats = {}
    for xmlid, menu, kind in ACTIONS:
        outcomes = Counter()
        first = None
        for user in users:
            company = user.company_id if user.company_id in user.company_ids else user.company_ids[0]
            scope = shell(user=user.id, su=False, context={"allowed_company_ids": [company.id]})
            assert not scope.su and scope.company == company
            try:
                observed = open_action(scope, xmlid, menu, kind)
            except AccessError:
                outcomes["denied"] += 1
                continue
            if not observed:
                outcomes["hidden_or_empty"] += 1
                continue
            outcomes["opened"] += 1
            if first is None:
                first = observed
        stats[kind] = {"operators": dict(outcomes), "form": first}
    shell.cr.rollback()
    return {"operators": len(users), "original_settings_members": len(users.filtered(
        lambda user: user.has_group("base.group_system"))), "actions": stats}
