# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrTerminationNotice(models.Model):
    """Carta de aviso de término de contrato (art. 162 Código del
    Trabajo). Distinta del Registro de término de contrato: aquí se
    modelan por separado sus estados y comprobantes, tal como exige el
    encargo."""

    _name = "hr.termination.notice"
    _description = "Carta de aviso de término de contrato"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("Nuevo"), copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    contract_id = fields.Many2one("hr.contract", required=True, tracking=True)
    employee_id = fields.Many2one(related="contract_id.employee_id", store=True)

    causal_id = fields.Many2one("step.hr.termination.cause", required=True, tracking=True)
    hechos_causal = fields.Text(
        string="Hechos que fundamentan la causal",
        help="Máximo 200 caracteres exigido por la DT.",
    )
    certificate_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Certificado / adjunto exigido",
        help="Obligatorio cuando la causal lo exige (ej. art. 163 bis).",
    )

    date_termino = fields.Date(string="Fecha de término", required=True, tracking=True)
    date_notificacion = fields.Date(string="Fecha de notificación", tracking=True)
    medio_notificacion = fields.Selection(
        [("personal", "Entrega personal"), ("correo", "Carta certificada")],
        string="Medio de notificación",
        tracking=True,
    )
    oficina_correos = fields.Char(string="Oficina de correos")

    monto_anio_servicio = fields.Monetary(string="Monto indemnización años de servicio")
    monto_aviso_previo = fields.Monetary(string="Monto indemnización sustitutiva de aviso previo")
    currency_id = fields.Many2one(related="company_id.currency_id")

    estado_cotizaciones = fields.Text(string="Estado de las cotizaciones previsionales")
    tipo_doc_cotizaciones = fields.Selection(
        [
            ("0", "Copias de las planillas de cotizaciones previsionales"),
            ("1", "Certificado emitido por el organismo previsional"),
            ("2", "No corresponde informar"),
        ],
        string="Tipo de documento de cotizaciones",
    )

    finiquito_modalidad_propuesta = fields.Selection(
        [("presencial", "Presencial"), ("electronico", "Electrónico")],
        default="electronico",
        string="Modalidad de finiquito propuesta",
    )
    reserva_derechos = fields.Boolean(string="Reserva de derechos")

    notice_deadline_days = fields.Integer(
        related="causal_id.notice_deadline_days", string="Plazo (días)"
    )
    deadline_date = fields.Date(compute="_compute_deadline", store=True)
    is_late = fields.Boolean(compute="_compute_deadline", store=True)

    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("notified", "Notificada"),
            ("cancelled", "Cancelada"),
        ],
        default="draft",
        tracking=True,
    )
    registration_state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("file_generated", "Archivo generado"),
            ("submitted", "Presentado"),
            ("accepted", "Aceptado"),
            ("observed_rejected", "Observado / rechazado"),
        ],
        default="pending",
        tracking=True,
        string="Estado registro de término (DT)",
    )
    document_id = fields.Many2one("hr.labor.document", readonly=True)
    delivery_receipt_id = fields.Many2one(
        "ir.attachment", string="Acuse / comprobante de entrega"
    )
    cancel_reason = fields.Text()

    @api.depends("date_termino", "causal_id.notice_deadline_days", "date_notificacion")
    def _compute_deadline(self):
        for notice in self:
            if notice.date_termino and notice.notice_deadline_days:
                notice.deadline_date = notice.date_termino + timedelta(
                    days=notice.notice_deadline_days
                )
            else:
                notice.deadline_date = False
            today = fields.Date.context_today(notice)
            reference = notice.date_notificacion or today
            notice.is_late = bool(
                notice.deadline_date
                and reference > notice.deadline_date
                and notice.state != "notified"
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hr.termination.notice"
                ) or _("Nuevo")
        return super().create(vals_list)

    def action_generate_letter(self):
        self.ensure_one()
        if self.causal_id.requires_certificate and not self.certificate_attachment_id:
            raise UserError(
                _(
                    "La causal '%s' exige adjuntar un certificado antes de "
                    "notificar el aviso."
                )
                % self.causal_id.name
            )
        template = self.env["hr.labor.template"].search(
            [
                ("document_type", "=", "notice"),
                ("company_id", "=", self.company_id.id),
                ("state", "=", "validated"),
            ],
            limit=1,
        )
        if not template:
            raise UserError(_("No hay una plantilla de carta de aviso validada."))
        doc = self.env["hr.labor.document"].generate_from_template(
            self.contract_id, template, "notice"
        )
        self.write({"document_id": doc.id})
        return doc

    def action_mark_notified(self):
        for notice in self:
            if not notice.date_notificacion or not notice.medio_notificacion:
                raise UserError(
                    _("Indique fecha y medio de notificación antes de marcarla.")
                )
            notice.state = "notified"

    def action_cancel(self):
        for notice in self:
            if not notice.cancel_reason:
                raise UserError(_("Indique el motivo de cancelación."))
            notice.state = "cancelled"
