from odoo import _
from odoo.exceptions import UserError


def pre_init_hook(env):
    providers = env["ir.module.module"].search_count([
        ("name", "in", ["helpdesk", "helpdesk_mgmt"]), ("state", "in", ["installed", "to install", "to upgrade"])
    ])
    if providers:
        raise UserError(_("Ya hay otro proveedor activo de los tickets."))
    for model in ("helpdesk.ticket", "helpdesk.team", "helpdesk.stage", "helpdesk.tag"):
        env.cr.execute("SELECT to_regclass(%s)", ("public."+model.replace(".", "_"),))
        if not env.cr.fetchone()[0] or not env["ir.model"].search_count([("model", "=", model)]):
            raise UserError(_("Falta el modelo histórico %s.", model))
    for xmlid in ("helpdesk.group_helpdesk_user", "helpdesk.group_helpdesk_manager",
                  "helpdesk.helpdesk_ticket_menu_my", "helpdesk.helpdesk_ticket_menu_all"):
        if not env.ref(xmlid, raise_if_not_found=False):
            raise UserError(_("Falta la referencia de soporte %s.", xmlid))
    env.cr.execute("SELECT count(*) FROM ir_sequence WHERE active AND code='helpdesk.ticket'")
    if not env.cr.fetchone()[0]:
        raise UserError(_("Falta la secuencia de tickets de la instalación original."))
