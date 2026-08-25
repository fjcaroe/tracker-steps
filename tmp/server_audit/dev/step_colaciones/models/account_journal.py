from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_colaciones_provision_journal = fields.Boolean(
        string="Diario de provisión de colaciones",
        compute="_compute_is_colaciones_provision_journal",
        inverse="_inverse_is_colaciones_provision_journal",
        help=(
            "Al activarlo, este diario se utilizará para los comprobantes de "
            "colaciones de la compañía. Su cuenta predeterminada será la cuenta de abono."
        ),
    )

    @api.depends("company_id.colaciones_provision_journal_id")
    def _compute_is_colaciones_provision_journal(self):
        for journal in self:
            journal.is_colaciones_provision_journal = (
                journal.company_id.colaciones_provision_journal_id == journal
            )

    def _inverse_is_colaciones_provision_journal(self):
        for journal in self:
            if journal.is_colaciones_provision_journal:
                if journal.type not in ("general", "purchase"):
                    raise ValidationError(_(
                        "El diario de provisión de colaciones debe ser de tipo Misceláneo o Compras."
                    ))
                if not journal.default_account_id:
                    raise ValidationError(_(
                        "Defina primero la cuenta predeterminada que se utilizará como cuenta de abono."
                    ))
                journal.company_id.colaciones_provision_journal_id = journal
            elif journal.company_id.colaciones_provision_journal_id == journal:
                journal.company_id.colaciones_provision_journal_id = False
