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

import xlsxwriter

from odoo import _, api, fields, models
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

    bancoestado_export_count = fields.Integer(
        string="Exportaciones BancoEstado", default=0, readonly=True, copy=False,
    )

    @api.model
    def _bancoestado_clean_rut(self, vat):
        return re.sub(r"[^0-9Kk]", "", vat or "").upper()

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
        if self.batch_type != "outbound":
            raise UserError(_("BancoEstado sólo admite lotes de pagos salientes."))
        if not self.payment_ids:
            raise UserError(_("Agregue pagos al lote antes de exportarlo."))
        rows = []
        for payment in self.payment_ids.sorted(key=lambda item: (item.partner_id.name or "", item.id)):
            partner = payment.partner_id
            bank_account = payment.partner_bank_id
            if not partner.vat:
                raise UserError(_("El beneficiario %s no tiene RUT.") % partner.display_name)
            if not bank_account:
                raise UserError(_("El pago de %s no tiene una cuenta bancaria beneficiaria.") % partner.display_name)
            if not bank_account.bank_id:
                raise UserError(_("La cuenta %s no tiene banco asociado.") % bank_account.acc_number)
            account_number = re.sub(r"\D", "", bank_account.acc_number or "")
            if not account_number or len(account_number) > 17:
                raise UserError(_(
                    "La cuenta de %(partner)s debe contener sólo números y un máximo "
                    "de 17 dígitos.", partner=partner.display_name))
            method = bank_account.step_bancoestado_payment_method or "01"
            bank_code = self._bancoestado_bank_code(bank_account.bank_id)
            if method == "02" and bank_code != "012":
                raise UserError(_(
                    "La forma de pago 02 (cuenta de ahorro) sólo se permite para "
                    "cuentas BancoEstado, código 012."))
            rows.append((
                self._bancoestado_clean_rut(partner.vat), partner.name or partner.display_name,
                partner.email or "", bank_code, method, account_number, payment.amount,
            ))
        return rows

    def action_export_bancoestado_xlsx(self):
        """Genera el formato oficial Pago 7 Columnas de BancoEstado."""
        self.ensure_one()
        rows = self._bancoestado_rows()
        stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(stream, {"in_memory": True})
        sheet = workbook.add_worksheet("Pago 7 Columnas")
        header = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
        text_format = workbook.add_format({"num_format": "@"})
        amount_format = workbook.add_format({"num_format": "#,##0.00"})
        columns = [
            "RUT", "NOMBRES Y APELLIDOS O RAZÓN SOCIAL", "EMAIL", "BANCO",
            "FORMA DE PAGO", "N° DE CUENTA", "MONTO DEL PAGO",
        ]
        for column, title in enumerate(columns):
            sheet.write(0, column, title, header)
        for row_index, values in enumerate(rows, start=1):
            for column, value in enumerate(values):
                if column == 6:
                    sheet.write_number(row_index, column, value, amount_format)
                else:
                    sheet.write_string(row_index, column, str(value), text_format)
        sheet.set_column(0, 0, 14)
        sheet.set_column(1, 1, 42)
        sheet.set_column(2, 2, 32)
        sheet.set_column(3, 5, 18)
        sheet.set_column(6, 6, 20)
        sheet.freeze_panes(1, 0)
        workbook.close()
        safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", self.name or "lote")
        attachment = self.env["ir.attachment"].create({
            "name": "%s_BANCOESTADO_7_COLUMNAS.xlsx" % safe_name,
            "type": "binary", "datas": base64.b64encode(stream.getvalue()),
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
