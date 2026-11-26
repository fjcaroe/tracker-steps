import hashlib

from odoo import _, fields, models
from odoo.exceptions import UserError


class HrLaborDocument(models.Model):
    _inherit = "hr.labor.document"

    sign_oca_request_id = fields.Many2one(
        "sign.oca.request", string="Solicitud de firma", readonly=True,
        copy=False, check_company=True, ondelete="restrict",
    )
    sign_oca_state = fields.Selection(related="sign_oca_request_id.state", string="Estado de firma")

    def action_send_to_sign(self):
        self.ensure_one()
        self.check_access("write")
        # A concurrent click must reuse the same request after the RPC retry.
        self.env.cr.execute("SELECT id FROM hr_labor_document WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset(["state", "sign_oca_request_id"])
        request = self.sign_oca_request_id
        if not request:
            if self.state != "generated" or not self.pdf_attachment_id:
                raise UserError(_("Primero debe emitir el documento laboral."))
            pdf = self.pdf_attachment_id.with_context(bin_size=False)
            pdf.check_access("read")
            if not self.pdf_hash or hashlib.sha256(pdf.raw).hexdigest() != self.pdf_hash:
                raise UserError(_("El PDF no coincide con el documento emitido."))
            request = self.env["sign.oca.request"].with_company(self.company_id).create({
                "name": self.name,
                "filename": pdf.name,
                "data": pdf.datas,
                "company_id": self.company_id.id,
                "record_ref": "%s,%s" % (self._name, self.id),
            })
            self.sign_oca_request_id = request
        request.check_access("read")
        return request.get_formview_action()

    def action_cancel(self):
        for document in self:
            request = document.sign_oca_request_id
            if request and request.state in ("0_sent", "2_signed"):
                raise UserError(_("Resuelva primero la solicitud en Firma."))
        result = super().action_cancel()
        for request in self.mapped("sign_oca_request_id").filtered(lambda row: row.state == "1_draft"):
            request.cancel()
        return result
