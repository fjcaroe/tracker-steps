# -*- coding: utf-8 -*-
"""Extensión segura de pagos por lotes para Tesorería.

No existe todavía una especificación bancaria chilena aprobada. Por eso este
bridge sólo ofrece una revisión interna y una interfaz explícita para futuros
adaptadores; nunca presenta el CSV interno como archivo cargable al banco.
"""

import base64
import csv
import io

from odoo import _, api, models
from odoo.exceptions import UserError


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

    def action_export_treasury_review_csv(self):
        """CSV de control humano, deliberadamente incompatible con bancos."""
        self.ensure_one()
        if not self.payment_ids:
            raise UserError(_("Agregue pagos al lote antes de generar la revisión."))

        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
        writer.writerow(["DOCUMENTO INTERNO DE REVISION - NO CARGABLE AL BANCO"])
        writer.writerow(["Lote", self.name, "Fecha", self.date, "Tipo", self.batch_type])
        writer.writerow(["Referencia", "Tercero", "Fecha", "Moneda", "Importe", "Estado"])
        for payment in self.payment_ids.sorted(key=lambda item: (item.date, item.id)):
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
