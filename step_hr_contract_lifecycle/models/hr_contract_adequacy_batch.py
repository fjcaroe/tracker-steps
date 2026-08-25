# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrContractAdequacyBatch(models.Model):
    """Lote de adecuación de jornada preparado y aprobado con anticipación
    para una transición legal (por ejemplo, la reducción a 40 hrs de 2028).

    Preparar y aprobar un lote NO reduce la jornada de inmediato: sólo se
    aplica automáticamente el día en que la transición legal entra en
    vigencia (ver ``hr.legal.workweek.calendar._apply_transition``).
    """

    _name = "hr.contract.adequacy.batch"
    _description = "Lote de adecuación de jornada legal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("Nuevo"), copy=False, tracking=True)
    calendar_id = fields.Many2one(
        "hr.legal.workweek.calendar",
        string="Transición legal",
        required=True,
        tracking=True,
        domain=[("date_from", ">=", fields.Date.today())],
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, tracking=True
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("simulated", "Simulado"),
            ("approved", "Aprobado"),
            ("applied", "Aplicado"),
            ("cancelled", "Cancelado"),
        ],
        default="draft",
        tracking=True,
    )
    line_ids = fields.One2many(
        "hr.contract.adequacy.line", "batch_id", string="Contratos a adecuar"
    )
    line_count = fields.Integer(compute="_compute_line_count")
    approved_by = fields.Many2one("res.users", readonly=True, tracking=True)
    approved_date = fields.Datetime(readonly=True, tracking=True)
    notes = fields.Text(string="Análisis / distribución proporcional")

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hr.contract.adequacy.batch"
                ) or _("Nuevo")
        return super().create(vals_list)

    def action_simulate(self):
        for batch in self:
            if not batch.calendar_id:
                raise UserError(_("Seleccione la transición legal a simular."))
            Contract = self.env["hr.contract"]
            contracts = Contract.search(
                [("company_id", "=", batch.company_id.id), ("state", "=", "open")]
            )
            batch.line_ids.unlink()
            lines = []
            for contract in contracts:
                current = (
                    contract.resource_calendar_id.hours_per_week
                    if contract.resource_calendar_id
                    else 0.0
                )
                if current <= batch.calendar_id.max_weekly_hours:
                    continue
                lines.append(
                    (
                        0,
                        0,
                        {
                            "contract_id": contract.id,
                            "current_weekly_hours": current,
                            "new_weekly_hours": batch.calendar_id.max_weekly_hours,
                        },
                    )
                )
            batch.write({"line_ids": lines, "state": "simulated"})

    def action_approve(self):
        if not self.env.user.has_group(
            "step_hr_contract_lifecycle.group_contract_adequacy_approve"
        ):
            raise UserError(
                _("No tiene el permiso de aprobación de adecuación de jornada.")
            )
        for batch in self:
            if batch.state != "simulated":
                raise UserError(_("Sólo se puede aprobar un lote ya simulado."))
            if not batch.line_ids:
                raise UserError(_("El lote no tiene contratos afectados."))
            for line in batch.line_ids:
                if not line.distribution_note:
                    raise UserError(
                        _(
                            "El contrato de %s no tiene documentada la distribución "
                            "proporcional propuesta. Complétela antes de aprobar."
                        )
                        % line.contract_id.employee_id.name
                    )
            batch.write(
                {
                    "state": "approved",
                    "approved_by": self.env.user.id,
                    "approved_date": fields.Datetime.now(),
                }
            )

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_reset_draft(self):
        self.write({"state": "draft"})


class HrContractAdequacyLine(models.Model):
    _name = "hr.contract.adequacy.line"
    _description = "Línea de adecuación de jornada por contrato"

    batch_id = fields.Many2one(
        "hr.contract.adequacy.batch", required=True, ondelete="cascade"
    )
    contract_id = fields.Many2one("hr.contract", required=True, string="Contrato")
    employee_id = fields.Many2one(related="contract_id.employee_id", store=True)
    current_weekly_hours = fields.Float(string="Jornada actual (hrs/sem)")
    new_weekly_hours = fields.Float(string="Jornada adecuada (hrs/sem)")
    distribution_note = fields.Text(
        string="Distribución propuesta",
        help="Detalle de cómo se redistribuyen los días/turnos. Requiere "
        "acuerdo entre las partes cuando corresponda: adjunte el anexo "
        "firmado en el contrato antes de aprobar el lote.",
    )
    state = fields.Selection(
        [("pending", "Pendiente"), ("applied", "Aplicado"), ("exception", "Excepción")],
        default="pending",
    )
    applied_date = fields.Date(readonly=True)


class HrLegalCalendarExecutionLog(models.Model):
    """Bitácora inmutable de cada ejecución del calendario legal.

    Guarda valor anterior/nuevo, fecha efectiva, contrato afectado,
    excepciones y usuario/proceso — base para un rollback controlado
    (la restitución en sí se ejecuta desde un asistente dedicado, no
    automáticamente).
    """

    _name = "hr.legal.calendar.execution.log"
    _description = "Bitácora de ejecución del calendario legal"
    _order = "create_date desc"

    calendar_id = fields.Many2one("hr.legal.workweek.calendar", required=True)
    contract_id = fields.Many2one("hr.contract", required=True)
    old_hours = fields.Float()
    new_hours = fields.Float()
    effective_date = fields.Date(required=True)
    is_exception = fields.Boolean(
        string="Sin adecuación aprobada (incidencia)", default=False
    )
    adequacy_line_id = fields.Many2one("hr.contract.adequacy.line")
    user_id = fields.Many2one("res.users", string="Ejecutado por", required=True)
    rolled_back = fields.Boolean(default=False, readonly=True)

    def action_mark_rolled_back(self):
        for rec in self:
            rec.contract_id.message_post(
                body=_(
                    "Rollback controlado registrado para la ejecución del "
                    "%(date)s (de %(old)s a %(new)s hrs). Debe restituir "
                    "manualmente la jornada previa en el contrato."
                )
                % {"date": rec.effective_date, "old": rec.old_hours, "new": rec.new_hours}
            )
        self.write({"rolled_back": True})
