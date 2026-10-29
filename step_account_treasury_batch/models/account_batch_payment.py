# -*- coding: utf-8 -*-
"""Extensión segura de pagos por lotes para Tesorería.

No existe todavía una especificación bancaria chilena aprobada. Por eso este
bridge sólo ofrece una revisión interna y una interfaz explícita para futuros
adaptadores; nunca presenta el CSV interno como archivo cargable al banco.
"""

import base64
import csv
import io
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.step_bank_export_core.models.bank_export_service import clean_rut


class StepTreasuryBankExportAdapter(models.AbstractModel):
    _name = "step.treasury.bank.export.adapter"
    _description = "Interfaz versionada para exportación bancaria de Tesorería"

    adapter_code = "unconfigured"
    adapter_version = "0"

    @api.model
    def adapter_metadata(self):
        return {
            "code": self.adapter_code,
            "version": self.adapter_version,
            "enabled": False,
            "reason": _("No existe un formato bancario aprobado para esta empresa."),
        }

    @api.model
    def export_bank_file(self, batch):
        raise UserError(_(
            "No hay un adaptador bancario aprobado. Use únicamente la revisión "
            "interna; ese archivo no es cargable al banco."))


class AccountBatchPayment(models.Model):
    _inherit = "account.batch.payment"

    bancoestado_export_count = fields.Integer(
        string="Exportaciones BancoEstado", default=0, readonly=True, copy=False,
    )
    approval_required = fields.Boolean(
        string="Requiere aprobación", compute="_compute_approval_required",
        help="El total del lote supera el tope configurado en Tesorería.",
    )
    approved_by_id = fields.Many2one(
        "res.users", string="Aprobado por", readonly=True, copy=False,
    )
    approved_date = fields.Datetime(string="Fecha de aprobación", readonly=True, copy=False)

    @api.depends("amount", "company_id", "batch_type")
    def _compute_approval_required(self):
        for batch in self:
            threshold = batch.company_id.treasury_batch_approval_threshold
            # `amount` viene con signo (negativo en lotes salientes): se
            # compara el monto absoluto contra el tope configurado.
            batch.approval_required = bool(
                batch.batch_type == "outbound" and threshold and abs(batch.amount) > threshold
            )

    def action_approve_batch(self):
        self.ensure_one()
        approver = self.company_id.treasury_batch_approver_id
        if not approver:
            raise UserError(_(
                "No hay un aprobador configurado en Tesorería → Configuración → "
                "Aprobación de lotes."))
        if self.env.user != approver:
            raise UserError(_(
                "Sólo %s puede aprobar este lote.") % approver.display_name)
        self.write({
            "approved_by_id": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })
        self.message_post(body=_(
            "Lote aprobado por %(user)s (monto %(amount)s, supera el tope de "
            "%(threshold)s configurado en Tesorería).",
            user=self.env.user.display_name, amount=abs(self.amount),
            threshold=self.company_id.treasury_batch_approval_threshold))

    def _check_batch_approval(self):
        self.ensure_one()
        if self.approval_required and not self.approved_by_id:
            approver = self.company_id.treasury_batch_approver_id
            raise UserError(_(
                "El lote %(name)s supera el tope de %(threshold)s configurado en "
                "Tesorería y requiere aprobación de %(approver)s antes de exportarlo.",
                name=self.name or "", threshold=self.company_id.treasury_batch_approval_threshold,
                approver=approver.display_name if approver else _("(sin aprobador configurado)")))

    @api.model
    def _bancoestado_clean_rut(self, vat):
        return clean_rut(vat)

    @api.model
    def _bancoestado_bank_code(self, bank):
        code = re.sub(r"\D", "", bank.bic or "")
        if len(code) != 3:
            raise UserError(_(
                "El banco %(bank)s debe tener su código BancoEstado/SBIF de tres "
                "dígitos en el campo BIC/SWIFT.", bank=bank.display_name))
        return code

    def _bancoestado_rows(self):
        self.ensure_one()
        self.check_access('write')
        if self.batch_type != "outbound":
            raise UserError(_("BancoEstado sólo admite lotes de pagos salientes."))
        self._check_batch_approval()
        return self.env['step.bank.export.service'].bancoestado_rows(self._treasury_export_payments(), self.company_id)

    def _treasury_export_payments(self):
        """Retain the full original batch selection when payment rules filter UI."""
        self.ensure_one()
        self.check_access('write')
        self.env.cr.execute('SELECT id FROM account_payment WHERE batch_payment_id=%s ORDER BY id', [self.id])
        payments = self.env['account.payment'].browse([row[0] for row in self.env.cr.fetchall()])
        payments.check_access('read')
        return payments

    def action_export_bancoestado_xlsx(self):
        """Genera el formato oficial Pago 7 Columnas de BancoEstado."""
        self.ensure_one()
        rows = self._bancoestado_rows()
        payload = self.env['step.bank.export.service'].bancoestado_file(self._treasury_export_payments(), self.company_id)
        safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", self.name or "lote")
        attachment = self.env["ir.attachment"].create({
            "name": "%s_BANCOESTADO_7_COLUMNAS.xlsx" % safe_name,
            "type": "binary", "datas": base64.b64encode(payload),
            "res_model": self._name, "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })
        self.bancoestado_export_count += 1
        self.message_post(body=_(
            "Archivo BancoEstado Pago 7 Columnas generado por %(user)s con %(count)s pagos.",
            user=self.env.user.display_name, count=len(rows)))
        return {"type": "ir.actions.act_url",
                "url": "/web/content/%s?download=true" % attachment.id, "target": "self"}

    def action_export_treasury_review_csv(self):
        """CSV de control humano, deliberadamente incompatible con bancos."""
        self.ensure_one()
        self.check_access('write')
        payments = self._treasury_export_payments()
        if not payments:
            raise UserError(_("Agregue pagos al lote antes de generar la revisión."))

        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
        writer.writerow(["DOCUMENTO INTERNO DE REVISION - NO CARGABLE AL BANCO"])
        writer.writerow(["Lote", self.name, "Fecha", self.date, "Tipo", self.batch_type])
        writer.writerow(["Referencia", "Tercero", "Fecha", "Moneda", "Importe", "Estado"])
        for payment in payments.sorted(key=lambda item: (item.date, item.id)):
            writer.writerow([
                payment.name or payment.memo or "",
                payment.partner_id.display_name or "",
                payment.date or "",
                payment.currency_id.name or "",
                "%.2f" % (payment.amount or 0.0),
                payment.state or "",
            ])

        payload = stream.getvalue().encode("utf-8-sig")
        attachment = self.env["ir.attachment"].create({
            "name": "%s_REVISION_INTERNA_NO_BANCO.csv" % (self.name or "lote"),
            "type": "binary",
            "datas": base64.b64encode(payload),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "text/csv",
        })
        self.message_post(body=_(
            "Revisión interna generada por %s. No es un archivo bancario.")
            % self.env.user.display_name)
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }
