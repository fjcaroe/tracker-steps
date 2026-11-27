from odoo import _
from odoo.exceptions import UserError


def pre_init_hook(env):
    if env["ir.module.module"].search_count([
        ("name", "=", "documents"), ("state", "in", ["installed", "to install", "to upgrade"]),
    ]):
        raise UserError(_("El proveedor anterior de Documentos sigue activo."))
    env.cr.execute("SELECT to_regclass('documents_document'), to_regclass('documents_access')")
    if not all(env.cr.fetchone()) or not all(env.ref(xmlid, raise_if_not_found=False) for xmlid in (
        "documents.dashboard", "documents.group_documents_manager", "documents.group_documents_system",
    )):
        raise UserError(_("Esta integración requiere la biblioteca original restaurada y sus grupos."))
