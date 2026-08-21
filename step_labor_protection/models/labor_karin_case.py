from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StepLaborKarinCase(models.Model):
    _name = "step.labor.karin.case"
    _description = "Caso confidencial Ley Karin"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "report_date desc, id desc"
    _rec_name = "reference"

    reference = fields.Char(
        string="Folio", required=True, readonly=True, copy=False, default=lambda self: _("Nuevo"), index=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company,
        index=True, tracking=True,
    )
    report_date = fields.Date(
        string="Fecha de recepción", required=True, default=fields.Date.context_today, tracking=True, index=True,
    )
    reception_channel = fields.Selection(
        [("written", "Escrita"), ("verbal", "Verbal"), ("email", "Correo electrónico"),
         ("web", "Canal digital"), ("dt", "Derivada por DT"), ("other", "Otro")],
        string="Canal de recepción", required=True, default="written", tracking=True,
    )
    case_type = fields.Selection(
        [("workplace_harassment", "Acoso laboral"), ("sexual_harassment", "Acoso sexual"),
         ("third_party_violence", "Violencia de terceros"), ("gender_violence", "Violencia de género"),
         ("other", "Otro hecho a evaluar")],
        string="Tipo de situación", required=True, tracking=True, index=True,
    )
    summary = fields.Char(string="Resumen reservado", required=True, tracking=True)
    description = fields.Html(string="Relato de los hechos", required=True)
    affected_employee_id = fields.Many2one("hr.employee", string="Persona afectada", tracking=True)
    reporter_employee_id = fields.Many2one("hr.employee", string="Persona denunciante", tracking=True)
    reporter_name = fields.Char(string="Denunciante externo/a", tracking=True)
    reported_employee_id = fields.Many2one("hr.employee", string="Persona denunciada", tracking=True)
    reported_third_party = fields.Char(string="Tercero denunciado", tracking=True)
    verbal_record_signed = fields.Boolean(
        string="Acta verbal firmada", tracking=True,
        help="Para denuncias verbales, confirme que se levantó un acta y fue entregada para firma.",
    )
    no_retaliation_explained = fields.Boolean(string="Protección contra represalias informada", tracking=True)
    confidentiality_explained = fields.Boolean(string="Confidencialidad informada", tracking=True)
    investigator_id = fields.Many2one("res.users", string="Responsable del caso", tracking=True)
    route = fields.Selection(
        [("pending", "Por definir"), ("internal", "Investigación interna"), ("dt", "Derivación a DT")],
        string="Vía de investigación", required=True, default="pending", tracking=True, index=True,
    )
    route_decision_date = fields.Date(string="Fecha decisión/derivación", tracking=True)
    dt_folio = fields.Char(string="Folio DT", tracking=True)
    investigation_start_date = fields.Date(string="Inicio investigación", tracking=True)
    investigation_end_date = fields.Date(string="Conclusiones emitidas", tracking=True)
    measures_applied_date = fields.Date(string="Medidas/sanciones aplicadas", tracking=True)
    conclusion = fields.Html(string="Conclusiones y fundamentos")
    resolution = fields.Html(string="Medidas o sanciones")
    attachment_ids = fields.Many2many(
        "ir.attachment", "step_labor_karin_attachment_rel", "case_id", "attachment_id",
        string="Antecedentes reservados",
    )
    safeguard_ids = fields.One2many("step.labor.karin.safeguard", "case_id", string="Medidas de resguardo")
    event_ids = fields.One2many("step.labor.karin.event", "case_id", string="Bitácora de investigación")
    state = fields.Selection(
        [("received", "Recibida"), ("safeguards", "Resguardos"), ("investigation", "En investigación"),
         ("resolution", "En resolución"), ("closed", "Cerrada"), ("discarded", "No admisible")],
        string="Estado", required=True, default="received", tracking=True, index=True,
    )
    route_deadline = fields.Date(string="Plazo decisión (3 días)", compute="_compute_deadlines", store=True)
    investigation_deadline = fields.Date(string="Plazo investigación (30 días)", compute="_compute_deadlines", store=True)
    measures_deadline = fields.Date(string="Plazo medidas (15 días)", compute="_compute_deadlines", store=True)
    deadline_status = fields.Selection(
        [("ok", "Al día"), ("soon", "Próximo a vencer"), ("overdue", "Vencido"), ("done", "Completado")],
        string="Control de plazo", compute="_compute_deadline_status", search="_search_deadline_status",
    )
    active = fields.Boolean(default=True)

    @api.depends("report_date", "route_decision_date", "investigation_start_date", "investigation_end_date")
    def _compute_deadlines(self):
        for record in self:
            record.route_deadline = record.report_date + timedelta(days=3) if record.report_date else False
            start = record.investigation_start_date or record.route_decision_date
            record.investigation_deadline = start + timedelta(days=30) if start else False
            record.measures_deadline = record.investigation_end_date + timedelta(days=15) if record.investigation_end_date else False

    @api.depends("state", "route", "route_decision_date", "route_deadline", "investigation_end_date",
                 "investigation_deadline", "measures_applied_date", "measures_deadline")
    def _compute_deadline_status(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state in ("closed", "discarded"):
                record.deadline_status = "done"
                continue
            deadline = False
            completed = False
            if record.route == "pending":
                deadline, completed = record.route_deadline, record.route_decision_date
            elif not record.investigation_end_date:
                deadline, completed = record.investigation_deadline, record.investigation_end_date
            else:
                deadline, completed = record.measures_deadline, record.measures_applied_date
            if completed:
                record.deadline_status = "done"
            elif deadline and deadline < today:
                record.deadline_status = "overdue"
            elif deadline and (deadline - today).days <= 5:
                record.deadline_status = "soon"
            else:
                record.deadline_status = "ok"

    def _search_deadline_status(self, operator, value):
        records = self.search([]).filtered(lambda r: r.deadline_status == value)
        return [("id", "in" if operator in ("=", "in") else "not in", records.ids)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("Nuevo")) == _("Nuevo"):
                vals["reference"] = self.env["ir.sequence"].next_by_code("step.labor.karin.case") or _("Nuevo")
        return super().create(vals_list)

    @api.constrains("reception_channel", "verbal_record_signed")
    def _check_verbal_record(self):
        for record in self:
            if record.reception_channel == "verbal" and record.state != "received" and not record.verbal_record_signed:
                raise ValidationError("Antes de avanzar una denuncia verbal debe confirmar el acta firmada.")

    def action_apply_safeguards(self):
        for record in self:
            if not record.safeguard_ids:
                raise UserError("Registre al menos una medida de resguardo antes de continuar.")
            record.write({"state": "safeguards"})

    def action_start_investigation(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.route == "pending":
                raise UserError("Seleccione investigación interna o derivación a la DT.")
            record.write({
                "state": "investigation",
                "route_decision_date": record.route_decision_date or today,
                "investigation_start_date": record.investigation_start_date or today,
            })

    def action_resolve(self):
        today = fields.Date.context_today(self)
        for record in self:
            if not record.conclusion:
                raise UserError("Registre las conclusiones antes de pasar a resolución.")
            record.write({"state": "resolution", "investigation_end_date": record.investigation_end_date or today})

    def action_close(self):
        today = fields.Date.context_today(self)
        for record in self:
            if not record.resolution:
                raise UserError("Registre las medidas o sanciones antes de cerrar el caso.")
            record.write({"state": "closed", "measures_applied_date": record.measures_applied_date or today})

    def action_discard(self):
        self.write({"state": "discarded"})

    def action_reopen(self):
        self.write({"state": "received"})


class StepLaborKarinSafeguard(models.Model):
    _name = "step.labor.karin.safeguard"
    _description = "Medida de resguardo Ley Karin"
    _order = "start_date desc, id desc"

    case_id = fields.Many2one("step.labor.karin.case", required=True, ondelete="cascade", index=True)
    measure_type = fields.Selection(
        [("separation", "Separación física"), ("schedule", "Redistribución de jornada"),
         ("remote", "Trabajo remoto"), ("psychological", "Atención psicológica temprana"),
         ("no_contact", "Prohibición de contacto"), ("leave", "Permiso o licencia"), ("other", "Otra")],
        string="Medida", required=True,
    )
    description = fields.Char(string="Detalle", required=True)
    responsible_id = fields.Many2one("res.users", string="Responsable", required=True, default=lambda self: self.env.user)
    start_date = fields.Date(string="Inicio", required=True, default=fields.Date.context_today)
    end_date = fields.Date(string="Término")
    state = fields.Selection([("active", "Vigente"), ("done", "Finalizada")], default="active", required=True)
    non_detriment_confirmed = fields.Boolean(string="Sin menoscabo para la persona denunciante")


class StepLaborKarinEvent(models.Model):
    _name = "step.labor.karin.event"
    _description = "Hito de investigación Ley Karin"
    _order = "date desc, id desc"

    case_id = fields.Many2one("step.labor.karin.case", required=True, ondelete="cascade", index=True)
    date = fields.Datetime(string="Fecha y hora", required=True, default=fields.Datetime.now)
    event_type = fields.Selection(
        [("reception", "Recepción"), ("interview", "Entrevista"), ("evidence", "Antecedente"),
         ("notification", "Notificación"), ("dt", "Gestión ante DT"), ("decision", "Decisión"),
         ("followup", "Seguimiento")],
        required=True, string="Tipo",
    )
    description = fields.Text(string="Descripción", required=True)
    responsible_id = fields.Many2one("res.users", string="Registrado por", required=True, default=lambda self: self.env.user)
    attachment = fields.Binary(string="Archivo", attachment=True)
    attachment_filename = fields.Char(string="Nombre del archivo")

