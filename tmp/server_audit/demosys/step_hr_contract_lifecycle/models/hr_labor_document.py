# -*- coding: utf-8 -*-
import base64
import hashlib

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrLaborDocument(models.Model):
    """Documento laboral emitido: snapshot congelado del texto, PDF, hash,
    usuario y fecha. Editar la plantilla de origen después de emitido NO
    modifica este registro."""

    _name = "hr.labor.document"
    _description = "Documento laboral emitido (contrato / aviso / finiquito)"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("Nuevo"), copy=False, tracking=True)
    document_type = fields.Selection(
        [
            ("contract", "Contrato"),
            ("notice", "Carta de aviso"),
            ("severance", "Finiquito"),
        ],
        required=True,
    )
    template_id = fields.Many2one("hr.labor.template", required=True)
    template_version = fields.Integer(readonly=True)
    contract_id = fields.Many2one("hr.contract", string="Contrato", index=True)
    employee_id = fields.Many2one(related="contract_id.employee_id", store=True)
    company_id = fields.Many2one(related="contract_id.company_id", store=True)
    rendered_body_html = fields.Html(readonly=True)
    pdf_attachment_id = fields.Many2one("ir.attachment", readonly=True)
    pdf_hash = fields.Char(readonly=True)
    generated_by = fields.Many2one("res.users", readonly=True)
    generated_date = fields.Datetime(readonly=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("generated", "Generado"),
            ("sent_to_sign", "Enviado a firma"),
            ("signed", "Firmado"),
            ("cancelled", "Cancelado"),
        ],
        default="draft",
        tracking=True,
    )
    cancel_reason = fields.Text()
    sign_reference = fields.Char(
        string="Referencia de firma",
        help="Id del sign.request si el módulo Firma está instalado.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                code = {
                    "contract": "hr.labor.document.contract",
                    "notice": "hr.labor.document.notice",
                    "severance": "hr.labor.document.severance",
                }.get(vals.get("document_type"), "hr.labor.document")
                vals["name"] = self.env["ir.sequence"].next_by_code(code) or _("Nuevo")
        return super().create(vals_list)

    @api.model
    def generate_from_template(self, contract, template, document_type):
        if template.state != "validated":
            raise UserError(_("La plantilla '%s' no está validada.") % template.name)
        rendered = template.render(contract)
        doc = self.create(
            {
                "document_type": document_type,
                "template_id": template.id,
                "template_version": template.version,
                "contract_id": contract.id,
                "rendered_body_html": rendered,
                "generated_by": self.env.user.id,
                "generated_date": fields.Datetime.now(),
                "state": "generated",
            }
        )
        report_action = self.env.ref(
            "step_hr_contract_lifecycle.action_report_hr_labor_document"
        )
        pdf_content, _dummy = report_action._render_qweb_pdf(
            "step_hr_contract_lifecycle.action_report_hr_labor_document", doc.ids
        )
        pdf_hash = hashlib.sha256(pdf_content).hexdigest()
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"{doc.name}.pdf",
                "type": "binary",
                "datas": base64.b64encode(pdf_content) if pdf_content else False,
                "res_model": "hr.labor.document",
                "res_id": doc.id,
                "mimetype": "application/pdf",
            }
        )
        doc.write({"pdf_attachment_id": attachment.id, "pdf_hash": pdf_hash})
        contract.message_post(
            body=_("Documento %s generado (plantilla %s v%s).")
            % (doc.name, template.name, template.version),
            attachment_ids=[attachment.id],
        )
        if contract.employee_id:
            contract.employee_id.message_post(
                body=_("Documento %s generado.") % doc.name,
                attachment_ids=[attachment.id],
            )
        return doc

    def action_cancel(self):
        for doc in self:
            if not doc.cancel_reason:
                raise UserError(_("Indique el motivo de la cancelación."))
            doc.state = "cancelled"

    def action_send_to_sign(self):
        self.ensure_one()
        if "sign.request" not in self.env:
            raise UserError(
                _(
                    "El módulo Firma no está instalado en esta instancia. "
                    "El documento sigue disponible como PDF para firma manual."
                )
            )
        if not self.pdf_attachment_id:
            raise UserError(_("El documento no tiene PDF generado."))
        sign_request = self.env["sign.request"].create(
            {
                "template_id": False,
                "reference": self.name,
                "request_item_ids": [],
            }
        )
        self.write({"sign_reference": str(sign_request.id), "state": "sent_to_sign"})
        return {
            "type": "ir.actions.act_window",
            "res_model": "sign.request",
            "res_id": sign_request.id,
            "view_mode": "form",
        }
