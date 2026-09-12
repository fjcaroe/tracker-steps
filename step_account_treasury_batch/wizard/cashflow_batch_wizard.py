# -*- coding: utf-8 -*-
"""Generación de un lote de pago desde la planificación de Tesorería.

No hay una segunda fuente de cifras: el proceso parte del mismo dataset
canónico del flujo (`step.cashflow.line`) y delega la creación de los pagos en
`account.payment.register`, el motor estándar de Odoo. Así las cuotas, los
pagos parciales y la conciliación se comportan exactamente igual que si el
usuario hubiera registrado cada pago a mano.
"""

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

from ..models.cashflow_batch import BATCH_SCOPES, SCOPE_BUCKETS


class StepCashflowBatchWizard(models.TransientModel):
    _name = "step.cashflow.batch.wizard"
    _description = "Crear lote de pago desde el flujo de caja"
    _check_company_auto = True

    cashflow_id = fields.Many2one(
        "step.cashflow", string="Flujo de caja", required=True, ondelete="cascade",
    )
    company_id = fields.Many2one(related="cashflow_id.company_id")
    currency_id = fields.Many2one(related="cashflow_id.currency_id")
    bucket_scope = fields.Selection(
        BATCH_SCOPES, string="Alcance", default="overdue_w1", required=True,
        help="Qué parte del horizonte se propone pagar. El requerimiento "
             "funcional parte de lo vencido más la semana 1.",
    )
    payment_date = fields.Date(
        string="Fecha de pago", required=True, default=fields.Date.context_today,
    )
    journal_id = fields.Many2one(
        "account.journal", string="Diario de banco", required=True, check_company=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
    )
    available_payment_method_line_ids = fields.Many2many(
        "account.payment.method.line", compute="_compute_available_payment_method_lines",
    )
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line", string="Método de pago", required=True,
        domain="[('id', 'in', available_payment_method_line_ids)]",
        help="Todos los pagos de un lote deben compartir el método de pago.",
    )
    batch_reference = fields.Char(
        string="Referencia del lote",
        help="Déjelo vacío para que Odoo numere el lote.",
    )
    candidate_line_ids = fields.Many2many(
        "step.cashflow.line", "step_cashflow_batch_candidate_rel", "wizard_id", "line_id",
        string="Documentos elegibles", compute="_compute_scope",
    )
    line_ids = fields.Many2many(
        "step.cashflow.line", "step_cashflow_batch_selected_rel", "wizard_id", "line_id",
        string="Documentos a pagar",
    )
    skipped_note = fields.Char(string="Descartados", compute="_compute_scope")
    payment_count = fields.Integer(string="Pagos a crear", compute="_compute_selection")
    amount_total = fields.Monetary(
        string="Total del lote", currency_field="currency_id", compute="_compute_selection",
    )

    # ------------------------------------------------------------------
    # Valores iniciales
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if not values.get("cashflow_id") and self.env.context.get("active_model") == "step.cashflow":
            values["cashflow_id"] = self.env.context.get("active_id")
        flow = self.env["step.cashflow"].browse(values.get("cashflow_id")).exists()
        if not flow:
            return values
        journal = flow.journal_ids.filtered(lambda item: item.type == "bank")[:1]
        if not journal:
            journal = self.env["account.journal"].search([
                ("company_id", "=", flow.company_id.id), ("type", "=", "bank"),
            ], limit=1)
        if journal:
            values.setdefault("journal_id", journal.id)
            method_line = journal.outbound_payment_method_line_ids[:1]
            if method_line:
                values.setdefault("payment_method_line_id", method_line.id)
        if "line_ids" in fields_list and not values.get("line_ids"):
            scope = values.get("bucket_scope") or "overdue_w1"
            payable = flow._batch_scope_lines(SCOPE_BUCKETS[scope])["payable"]
            values["line_ids"] = [Command.set(payable.ids)]
        return values

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends("journal_id")
    def _compute_available_payment_method_lines(self):
        for wizard in self:
            wizard.available_payment_method_line_ids = \
                wizard.journal_id.outbound_payment_method_line_ids

    @api.depends("cashflow_id", "bucket_scope")
    def _compute_scope(self):
        for wizard in self:
            if not wizard.cashflow_id:
                wizard.candidate_line_ids = False
                wizard.skipped_note = ""
                continue
            report = wizard.cashflow_id._batch_scope_lines(SCOPE_BUCKETS[wizard.bucket_scope])
            wizard.candidate_line_ids = [Command.set(report["payable"].ids)]
            notes = []
            if report["no_document"]:
                notes.append(_("%s sin factura publicada (órdenes, proformas o líneas manuales)")
                             % len(report["no_document"]))
            if report["already_batched"]:
                notes.append(_("%s ya incluidas en otro lote") % len(report["already_batched"]))
            if report["settled"]:
                notes.append(_("%s sin saldo pendiente") % len(report["settled"]))
            wizard.skipped_note = (_("Fuera del lote: %s.") % "; ".join(notes)) if notes else ""

    @api.depends("line_ids")
    def _compute_selection(self):
        for wizard in self:
            wizard.payment_count = len({line.source_id for line in wizard.line_ids})
            wizard.amount_total = sum(abs(line.amount_flow) for line in wizard.line_ids)

    @api.onchange("bucket_scope")
    def _onchange_bucket_scope(self):
        """Cambiar el alcance vuelve a proponer la selección completa."""
        self.line_ids = [Command.set(self.candidate_line_ids.ids)]

    @api.onchange("journal_id")
    def _onchange_journal(self):
        if self.payment_method_line_id not in self.journal_id.outbound_payment_method_line_ids:
            self.payment_method_line_id = self.journal_id.outbound_payment_method_line_ids[:1]

    # ------------------------------------------------------------------
    # Proceso
    # ------------------------------------------------------------------
    def _check_ready(self):
        self.ensure_one()
        if self.cashflow_id.state == "cancelled":
            raise UserError(_("Un flujo anulado no genera pagos."))
        if not self.line_ids:
            raise UserError(_("Seleccione al menos un documento a pagar."))
        if not self.env.user.has_group("account.group_account_invoice"):
            raise UserError(_(
                "Crear pagos requiere el perfil de facturación de Contabilidad."))
        foreign = self.line_ids.filtered(lambda line: line.cashflow_id != self.cashflow_id)
        if foreign:
            raise UserError(_("Hay líneas que no pertenecen al flujo %s.")
                            % self.cashflow_id.display_name)
        if self.payment_method_line_id not in self.journal_id.outbound_payment_method_line_ids:
            raise UserError(_("El método de pago no pertenece al diario %s.")
                            % self.journal_id.display_name)

    def action_create_batch(self):
        """Crea un pago por factura y los agrupa en un único lote saliente."""
        self.ensure_one()
        self._check_ready()

        by_move = {}
        for line in self.line_ids:
            grouped = by_move.setdefault(line.source_id, self.env["step.cashflow.line"])
            by_move[line.source_id] = grouped | line

        payments = self.env["account.payment"]
        assignments = []
        for move_id, lines in by_move.items():
            move = self.env["account.move"].browse(move_id).exists()
            if not move or move.state != "posted":
                raise UserError(_("El documento %s ya no es una factura publicada.")
                                % (lines[:1].doc_number or move_id))
            residual = abs(move.amount_residual)
            if float_is_zero(residual, precision_rounding=move.currency_id.rounding):
                raise UserError(_("La factura %s ya no tiene saldo pendiente.") % move.name)
            # Las líneas del flujo son cuotas: se paga lo seleccionado, nunca
            # más que el saldo real del documento al momento del pago.
            amount = sum(abs(line.amount_origin) for line in lines)
            if float_is_zero(amount, precision_rounding=move.currency_id.rounding) \
                    or float_compare(amount, residual,
                                     precision_rounding=move.currency_id.rounding) > 0:
                amount = residual
            register = self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=move.ids,
                dont_redirect_to_payments=True,
            ).create({
                "journal_id": self.journal_id.id,
                "payment_method_line_id": self.payment_method_line_id.id,
                "payment_date": self.payment_date,
                "currency_id": move.currency_id.id,
                "amount": amount,
                "group_payment": True,
                "payment_difference_handling": "open",
            })
            payment = register._create_payments()
            payments |= payment
            assignments.append((lines, payment))

        batch_values = {
            "batch_type": "outbound",
            "journal_id": self.journal_id.id,
            "date": self.payment_date,
            "payment_ids": [Command.set(payments.ids)],
        }
        if self.batch_reference:
            batch_values["name"] = self.batch_reference
        batch = self.env["account.batch.payment"].create(batch_values)

        for lines, payment in assignments:
            # El flujo aprobado es un snapshot congelado: anotar el lote es
            # trazabilidad, no un cambio en su base de cálculo.
            lines.with_context(treasury_bypass_lock=True).write({
                "treasury_payment_id": payment.id,
                "treasury_batch_id": batch.id,
            })

        self.cashflow_id.message_post(body=_(
            "Lote de pago %(batch)s generado desde el flujo: %(payments)s pagos "
            "por %(amount)s en %(journal)s.",
            batch=batch.name, payments=len(payments),
            amount=self.currency_id.round(self.amount_total),
            journal=self.journal_id.display_name))

        return {
            "type": "ir.actions.act_window",
            "name": _("Lote de pago"),
            "res_model": "account.batch.payment",
            "res_id": batch.id,
            "view_mode": "form",
            "target": "current",
        }
