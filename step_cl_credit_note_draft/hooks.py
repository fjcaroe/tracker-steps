from odoo import _
from odoo.exceptions import UserError


def pre_init_hook(env):
    view = env.ref("l10n_cl_edi.view_account_move_reversal", raise_if_not_found=False)
    parent = env.ref("l10n_latam_invoice_document.view_account_move_reversal")
    if not view or not view.active or view.model != "account.move.reversal" or view.inherit_id != parent:
        raise UserError(_("No se encontró la vista original del asistente de notas de crédito."))
    expected = {
        "l10n_cl_corrected_text": "character varying",
        "l10n_cl_edi_reference_doc_code": "character varying",
        "l10n_cl_is_text_correction": "boolean",
        "l10n_cl_original_text": "character varying",
    }
    env.cr.execute("""SELECT column_name, data_type FROM information_schema.columns
                       WHERE table_schema = 'public' AND table_name = 'account_move_reversal'
                         AND column_name IN %s""", [tuple(expected)])
    if dict(env.cr.fetchall()) != expected:
        raise UserError(_("Los campos originales del asistente de notas de crédito no coinciden con la copia."))
