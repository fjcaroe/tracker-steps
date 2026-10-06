"""Read posted contract installments using their original ledger lines."""
from odoo import _, models


class ProducerContractCashflow(models.Model):
    _inherit = "step.cashflow"

    def _collect_vendor(self):
        results = super()._collect_vendor()
        self.ensure_one()
        defaults = self._line_defaults("vendor")
        installments = self.env["step.producer.purchase.contract.installment"].search([
            ("company_id", "=", self.company_id.id), ("state", "!=", "accounted"),
            ("provision_line_id.parent_state", "=", "posted"),
        ])
        for installment in installments:
            entry = installment.provision_line_id
            contract = installment.contract_id
            if entry.company_id != self.company_id or entry.move_id != contract.accounting_move_id:
                continue
            currency = entry.currency_id or self.company_id.currency_id
            if entry.account_id.reconcile:
                amount = -(entry.amount_residual_currency if entry.currency_id else entry.amount_residual)
            else:
                amount = -(entry.amount_currency if entry.currency_id else entry.balance)
                reversal = installment.reversal_move_id
                if reversal and reversal.state == "posted" and reversal.company_id == self.company_id:
                    linked = self.env[installment._name].with_context(active_test=False).search_count([
                        ("reversal_move_id", "=", reversal.id)])
                    reverse_lines = reversal.line_ids.filtered(lambda line:
                        line.account_id == entry.account_id and line.partner_id == entry.partner_id
                        and line.currency_id == entry.currency_id
                        and (line.step_producer_installment_id == installment or linked == 1))
                    amount -= sum(reverse_lines.mapped("amount_currency" if entry.currency_id else "balance"))
            if amount <= 0 or currency.is_zero(amount):
                continue
            # A journal provision is a projection, not an invoice for the payment-lot wizard.
            results.append(dict(defaults, **{
                "source_model": contract._name, "source_id": contract.id,
                "source_line_id": entry.id, "partner_id": contract.partner_id.id,
                "partner_vat": contract.partner_id.vat or "",
                "doc_type_name": _("Anticipo de contrato"), "doc_number": contract.name,
                "doc_date": entry.move_id.date, "due_date": entry.date_maturity,
                "currency_id": currency.id, "amount_origin": currency.round(amount),
            }))
        return results
