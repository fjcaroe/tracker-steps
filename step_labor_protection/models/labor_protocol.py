from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StepLaborProtocol(models.Model):
    _name = "step.labor.protocol"
    _description = "Protocolo de prevención laboral"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "effective_date desc, id desc"

    name = fields.Char(string="Nombre", required=True, tracking=True)
    version = fields.Char(string="Versión", required=True, default="1.0", tracking=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True, tracking=True,
    )
    responsible_id = fields.Many2one(
        "res.users", string="Responsable", required=True,
        default=lambda self: self.env.user, tracking=True,
    )
    effective_date = fields.Date(string="Vigente desde", required=True, tracking=True)
    review_date = fields.Date(string="Próxima revisión", required=True, tracking=True)
    communication_date = fields.Date(string="Fecha de difusión", tracking=True)
    channel_description = fields.Text(
        string="Canales de denuncia",
        help="Indique canales presenciales, digitales y personas habilitadas para recibir denuncias.",
    )
    scope = fields.Html(string="Alcance y medidas preventivas")
    document = fields.Binary(string="Protocolo firmado", attachment=True)
    document_filename = fields.Char(string="Nombre del archivo")
    state = fields.Selection(
        [("draft", "Borrador"), ("active", "Vigente"), ("expired", "Reemplazado")],
        string="Estado", required=True, default="draft", tracking=True, index=True,
    )
    active = fields.Boolean(default=True)
    days_to_review = fields.Integer(string="Días para revisión", compute="_compute_review_status")
    review_status = fields.Selection(
        [("ok", "Al día"), ("soon", "Próximo a vencer"), ("overdue", "Vencido")],
        compute="_compute_review_status", string="Estado de revisión",
    )

    @api.depends("review_date")
    def _compute_review_status(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.days_to_review = (record.review_date - today).days if record.review_date else 0
            if not record.review_date or record.review_date < today:
                record.review_status = "overdue"
            elif record.days_to_review <= 30:
                record.review_status = "soon"
            else:
                record.review_status = "ok"

    @api.constrains("effective_date", "review_date")
    def _check_dates(self):
        for record in self:
            if record.review_date and record.effective_date and record.review_date <= record.effective_date:
                raise ValidationError("La próxima revisión debe ser posterior a la fecha de vigencia.")

    def action_activate(self):
        for record in self:
            others = self.search([
                ("company_id", "=", record.company_id.id),
                ("state", "=", "active"),
                ("id", "!=", record.id),
            ])
            others.write({"state": "expired"})
            record.write({"state": "active"})

    def action_set_draft(self):
        self.write({"state": "draft"})

