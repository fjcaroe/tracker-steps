# -*- coding: utf-8 -*-
import base64
import csv
import hashlib
import io

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .dt_contract_field_catalog import DT_CONTRACT_COLUMNS, build_row, validate_row


class HrContractDtBatch(models.Model):
    """Lote de carga masiva de contratos a la DT (Anexo A5).

    Una carga se agrupa por el mismo Cargo (job_id) y CAE, tal como exige
    el instructivo: por eso cada lote queda amarrado a un único
    (job_id, cae_code).
    """

    _name = "hr.contract.dt.batch"
    _description = "Lote DT — carga masiva de contratos"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("Nuevo"), copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    job_id = fields.Many2one("hr.job", required=True, string="Cargo")
    cae_code = fields.Char(string="CAE", required=True)
    contract_ids = fields.Many2many("hr.contract", string="Contratos incluidos")
    contract_count = fields.Integer(compute="_compute_contract_count")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("validated", "Validado"),
            ("generated", "Archivo generado"),
            ("submitted", "Presentado"),
            ("result_recorded", "Resultado registrado"),
        ],
        default="draft",
        tracking=True,
    )
    csv_attachment_id = fields.Many2one("ir.attachment", readonly=True)
    csv_hash = fields.Char(readonly=True)
    error_report = fields.Text(string="Errores de prevalidación", readonly=True)
    submitted_by = fields.Many2one("res.users", readonly=True)
    submitted_date = fields.Datetime(readonly=True)
    dt_result = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("accepted", "Aceptado"),
            ("observed", "Observado / rechazado"),
        ],
        default="pending",
        tracking=True,
        string="Resultado informado por el usuario",
    )
    dt_result_notes = fields.Text(string="Notas del resultado")
    dt_result_attachment_id = fields.Many2one(
        "ir.attachment", string="Comprobante DT"
    )

    @api.depends("contract_ids")
    def _compute_contract_count(self):
        for batch in self:
            batch.contract_count = len(batch.contract_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hr.contract.dt.batch"
                ) or _("Nuevo")
        return super().create(vals_list)

    def action_validate(self):
        for batch in self:
            if not batch.contract_ids:
                raise UserError(_("El lote no tiene contratos."))
            errors = []
            for contract in batch.contract_ids:
                missing = validate_row(contract)
                if missing:
                    errors.append(
                        "%s (%s): faltan %s"
                        % (
                            contract.employee_id.name or contract.display_name,
                            contract.id,
                            ", ".join(missing),
                        )
                    )
            batch.error_report = "\n".join(errors)
            batch.state = "draft" if errors else "validated"
            if errors:
                raise UserError(
                    _(
                        "Hay %(n)s contratos con datos faltantes. Revise el "
                        "campo 'Errores de prevalidación' antes de generar el "
                        "archivo:\n%(detail)s"
                    )
                    % {"n": len(errors), "detail": batch.error_report}
                )

    def action_generate_csv(self):
        self.ensure_one()
        if self.state != "validated":
            raise UserError(_("Valide el lote antes de generar el CSV."))
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        writer.writerow([col for col, _getter in DT_CONTRACT_COLUMNS])
        for contract in self.contract_ids:
            row = build_row(contract)
            writer.writerow([row[col] for col, _getter in DT_CONTRACT_COLUMNS])
        content = buffer.getvalue().encode("utf-8")
        rut_empleador = (self.company_id.vat or "SINRUT").replace(".", "").replace("-", "")
        period = fields.Date.context_today(self).strftime("%Y%m")
        filename = f"{rut_empleador}_{period}.csv"
        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "type": "binary",
                "datas": base64.b64encode(content),
                "res_model": "hr.contract.dt.batch",
                "res_id": self.id,
                "mimetype": "text/csv",
            }
        )
        self.write(
            {
                "csv_attachment_id": attachment.id,
                "csv_hash": hashlib.sha256(content).hexdigest(),
                "state": "generated",
            }
        )
        for contract in self.contract_ids:
            contract.dt_registration_state = "file_generated"

    def action_mark_submitted(self):
        self.write(
            {
                "state": "submitted",
                "submitted_by": self.env.user.id,
                "submitted_date": fields.Datetime.now(),
            }
        )
        for batch in self:
            for contract in batch.contract_ids:
                contract.dt_registration_state = "submitted"

    def action_record_result(self):
        for batch in self:
            if batch.dt_result == "pending":
                raise UserError(_("Indique si el lote fue aceptado u observado."))
            batch.state = "result_recorded"
            new_state = "accepted" if batch.dt_result == "accepted" else "observed_rejected"
            for contract in batch.contract_ids:
                contract.dt_registration_state = new_state
                if batch.dt_result_attachment_id:
                    contract.dt_receipt_attachment_id = batch.dt_result_attachment_id
