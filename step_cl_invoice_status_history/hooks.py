from odoo import _
from odoo.exceptions import UserError

from .models.account_move import STATUS


def pre_init_hook(env):
    if env["ir.module.module"].search_count([
        ("name", "=", "l10n_cl_edi"), ("state", "in", ["installed", "to install", "to upgrade"])
    ]):
        raise UserError(_("La instalación ya tiene un proveedor activo de DTE."))
    env.cr.execute("""SELECT column_name,data_type FROM information_schema.columns
                      WHERE table_schema='public' AND table_name='account_move'
                      AND column_name IN ('l10n_cl_dte_status','l10n_cl_dte_file','l10n_cl_sii_barcode')""")
    if dict(env.cr.fetchall()) != {"l10n_cl_dte_status":"character varying","l10n_cl_dte_file":"integer",
                                  "l10n_cl_sii_barcode":"character varying"}:
        raise UserError(_("Faltan los campos originales del estado, el archivo o el timbre del DTE."))
    env.cr.execute("SELECT to_regclass('public.l10n_cl_account_invoice_reference')")
    if not env.cr.fetchone()[0]:
        raise UserError(_("Falta la tabla original de referencias de los documentos tributarios."))
    env.cr.execute("SELECT DISTINCT l10n_cl_dte_status FROM account_move WHERE l10n_cl_dte_status IS NOT NULL")
    if {row[0] for row in env.cr.fetchall()} - dict(STATUS).keys():
        raise UserError(_("Hay estados de DTE de origen sin reconocer."))
