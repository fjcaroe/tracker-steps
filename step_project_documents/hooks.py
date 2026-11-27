from odoo import _
from odoo.exceptions import UserError


BUDGET_VIEW = "project_account_budget.project_project_kanban_view_inherited"


def post_init_hook(env):
    view = env.ref(BUDGET_VIEW, raise_if_not_found=False)
    if not view or "total_budget_amount" in env["project.project"]._fields:
        return
    provider = env["ir.module.module"].search([("name", "=", "project_account_budget")])
    if provider.state != "uninstalled" or view.model != "project.project" or view.mode != "extension":
        raise UserError(_("Antes de instalar, revise el proveedor de presupuestos de proyecto."))
    env.cr.execute("SELECT EXISTS (SELECT 1 FROM budget_analytic) OR EXISTS (SELECT 1 FROM budget_line)")
    if env.cr.fetchone()[0] or env["ir.ui.view"].search_count([("inherit_id", "=", view.id)]):
        raise UserError(_("Hay presupuestos o vistas dependientes que requieren su propia migración."))
    view.active = False
