from odoo import _
from odoo.exceptions import UserError


OCR_VIEWS = ("hr_expense_extract_view_form", "hr_expense_extract_view_graph",
             "hr_expense_extract_view_list", "hr_expense_extract_view_kanban")


def post_init_hook(env):
    views = env["ir.ui.view"]
    for name in OCR_VIEWS:
        view = env.ref("hr_expense_extract." + name, raise_if_not_found=False)
        if view:
            views |= view
    if not views or "extract_state" in env["hr.expense"]._fields:
        return
    provider = env["ir.module.module"].search([("name", "=", "hr_expense_extract")])
    if provider.state != "uninstalled" or any(view.model != "hr.expense" or view.mode != "extension" for view in views):
        raise UserError(_("Revise el proveedor de digitalización antes de instalar la integración de gastos."))
    env.cr.execute("""SELECT EXISTS (SELECT 1 FROM hr_expense WHERE extract_document_uuid IS NOT NULL
                      OR coalesce(extract_state, 'no_extract_requested') <> 'no_extract_requested')""")
    if env.cr.fetchone()[0] or env["ir.ui.view"].search_count([("inherit_id", "in", views.ids)]):
        raise UserError(_("Hay solicitudes de digitalización o vistas dependientes que requieren migración."))
    views.filtered("active").write({"active": False})
