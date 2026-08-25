# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

ALERT_THRESHOLDS = (180, 90, 60, 30, 15, 7)


class HrLegalWorkweekCalendar(models.Model):
    """Calendario legal versionado de jornada ordinaria máxima semanal.

    Nunca se lee un número de horas fijo disperso en el código: todo el
    resto del addon (contratos, plantillas, validaciones, dashboards)
    consulta ``get_effective_hours`` para saber el máximo legal vigente en
    una fecha y compañía dadas.
    """

    _name = "hr.legal.workweek.calendar"
    _description = "Calendario legal laboral (jornada máxima semanal)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc"
    _rec_name = "display_name"

    date_from = fields.Date(
        string="Vigente desde", required=True, tracking=True, index=True
    )
    max_weekly_hours = fields.Float(
        string="Jornada ordinaria máxima (hrs/semana)", required=True, tracking=True
    )
    legal_reference = fields.Char(string="Fuente normativa", tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        help="Vacío = aplica a todas las compañías (regla general nacional). "
        "Completar sólo si esta compañía tiene una excepción/pacto propio.",
        tracking=True,
    )
    is_official = fields.Boolean(
        string="Transición legal oficial",
        default=False,
        readonly=True,
        tracking=True,
        help="Filas precargadas desde la normativa vigente. No pueden "
        "editarse ni eliminarse por un usuario común.",
    )
    notes = fields.Text(string="Notas")
    display_name = fields.Char(compute="_compute_display_name", store=True)

    exception_reason = fields.Char(
        string="Motivo de la modificación excepcional",
        help="Obligatorio para editar/crear una fila luego de la carga "
        "inicial, o para editar cualquier fila oficial.",
    )

    @api.depends("date_from", "max_weekly_hours", "company_id")
    def _compute_display_name(self):
        for rec in self:
            company = rec.company_id.name if rec.company_id else _("Todas las compañías")
            rec.display_name = _("Desde %(date)s: %(hours)s hrs/semana (%(company)s)") % {
                "date": rec.date_from,
                "hours": rec.max_weekly_hours,
                "company": company,
            }

    _sql_constraints = [
        (
            "positive_hours",
            "CHECK(max_weekly_hours > 0)",
            "La jornada máxima semanal debe ser mayor que cero.",
        ),
    ]

    def _check_technical_permission(self, vals):
        touches_official = self.filtered("is_official")
        is_new_official = vals.get("is_official")
        needs_guard = touches_official or is_new_official
        if not needs_guard:
            return
        if not self.env.user.has_group(
            "step_hr_contract_lifecycle.group_legal_calendar_technical"
        ):
            raise UserError(
                _(
                    "Modificar una transición legal oficial requiere el permiso "
                    "técnico 'Calendario legal: configuración técnica'."
                )
            )
        reason = vals.get("exception_reason") or (self and self[:1].exception_reason)
        if not reason:
            raise UserError(
                _(
                    "Debe indicar un motivo (exception_reason) y la fuente normativa "
                    "para modificar una transición legal oficial."
                )
            )

    def write(self, vals):
        if any(f in vals for f in ("date_from", "max_weekly_hours", "is_official")):
            self._check_technical_permission(vals)
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.is_official and not self.env.user.has_group(
                "step_hr_contract_lifecycle.group_legal_calendar_technical"
            ):
                raise UserError(
                    _("No se puede eliminar una transición legal oficial (%s).")
                    % rec.display_name
                )
        return super().unlink()

    @api.model
    def get_effective_hours(self, date=None, company=None):
        """Devuelve (registro, horas) vigente en ``date`` para ``company``.

        Prioriza una fila específica de la compañía sobre la regla general
        (company_id vacío). No asume la fecha de hoy si no se indica.
        """
        date = date or fields.Date.context_today(self)
        company = company or self.env.company
        domain_specific = [("date_from", "<=", date), ("company_id", "=", company.id)]
        rec = self.search(domain_specific, order="date_from desc", limit=1)
        if not rec:
            domain_general = [("date_from", "<=", date), ("company_id", "=", False)]
            rec = self.search(domain_general, order="date_from desc", limit=1)
        if not rec:
            return self.browse(), 0.0
        return rec, rec.max_weekly_hours

    @api.model
    def get_upcoming_transition(self, date=None, company=None):
        """Próxima transición futura (para simulador/alertas)."""
        date = date or fields.Date.context_today(self)
        company = company or self.env.company
        domain = [
            ("date_from", ">", date),
            "|",
            ("company_id", "=", company.id),
            ("company_id", "=", False),
        ]
        return self.search(domain, order="date_from asc", limit=1)

    def _get_alert_responsible(self):
        company = self.company_id or self.env.company
        return company.legal_calendar_responsible_id or self.env.user

    def action_simulate(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Simulación de adecuación de jornada"),
            "res_model": "hr.legal.calendar.simulator",
            "view_mode": "form",
            "target": "new",
            "context": {"default_calendar_id": self.id},
        }

    @api.model
    def _cron_check_legal_calendar_transitions(self):
        """Job diario idempotente: alertas anticipadas + activación legal.

        - Para cada transición futura, si hoy coincide exactamente con uno
          de los umbrales de aviso, crea una actividad (no un correo) al
          responsable de RR. HH., una única vez por transición+umbral.
        - Para la transición cuya fecha_from es HOY, aplica las
          adecuaciones ya aprobadas y genera una incidencia crítica para
          los contratos vigentes sin adecuación aprobada.
        """
        today = fields.Date.context_today(self)
        upcoming = self.search([("date_from", ">=", today)])
        activity_type = self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        )
        for calendar in upcoming:
            days_left = (calendar.date_from - today).days
            if days_left in ALERT_THRESHOLDS:
                marker = _("legal-calendar-alert-%s-%s") % (calendar.id, days_left)
                existing = self.env["mail.activity"].search(
                    [
                        ("res_model", "=", "hr.legal.workweek.calendar"),
                        ("res_id", "=", calendar.id),
                        ("summary", "=", marker),
                    ],
                    limit=1,
                )
                if not existing:
                    calendar.activity_schedule(
                        act_type_xmlid="mail.mail_activity_data_todo",
                        summary=marker,
                        note=_(
                            "Faltan %(days)s días para que entre en vigencia la "
                            "jornada máxima de %(hours)s hrs/semana (%(date)s). "
                            "Revise el simulador y prepare/apruebe los lotes de "
                            "adecuación necesarios."
                        )
                        % {
                            "days": days_left,
                            "hours": calendar.max_weekly_hours,
                            "date": calendar.date_from,
                        },
                        user_id=calendar._get_alert_responsible().id,
                    )
            if days_left == 0:
                calendar._apply_transition()

    def _apply_transition(self):
        self.ensure_one()
        Contract = self.env["hr.contract"]
        Log = self.env["hr.legal.calendar.execution.log"]
        companies = self.company_id or self.env["res.company"].search([])
        for company in companies:
            _rec, new_max = self.get_effective_hours(self.date_from, company)
            contracts = Contract.search(
                [
                    ("company_id", "=", company.id),
                    ("state", "=", "open"),
                ]
            )
            for contract in contracts:
                current_hours = contract.resource_calendar_id.hours_per_week if contract.resource_calendar_id else 0.0
                if current_hours <= new_max:
                    continue
                line = self.env["hr.contract.adequacy.line"].search(
                    [
                        ("contract_id", "=", contract.id),
                        ("batch_id.calendar_id", "=", self.id),
                        ("batch_id.state", "=", "approved"),
                    ],
                    limit=1,
                )
                if line:
                    Log.create(
                        {
                            "calendar_id": self.id,
                            "contract_id": contract.id,
                            "old_hours": current_hours,
                            "new_hours": line.new_weekly_hours,
                            "effective_date": self.date_from,
                            "is_exception": False,
                            "adequacy_line_id": line.id,
                            "user_id": self.env.user.id,
                        }
                    )
                    line.write({"state": "applied", "applied_date": self.date_from})
                    contract.message_post(
                        body=_(
                            "Jornada semanal ajustada de %(old)s a %(new)s hrs por "
                            "adecuación aprobada (lote %(batch)s), vigencia legal "
                            "%(date)s."
                        )
                        % {
                            "old": current_hours,
                            "new": line.new_weekly_hours,
                            "batch": line.batch_id.name,
                            "date": self.date_from,
                        }
                    )
                else:
                    Log.create(
                        {
                            "calendar_id": self.id,
                            "contract_id": contract.id,
                            "old_hours": current_hours,
                            "new_hours": new_max,
                            "effective_date": self.date_from,
                            "is_exception": True,
                            "user_id": self.env.user.id,
                        }
                    )
                    contract.activity_schedule(
                        act_type_xmlid="mail.mail_activity_data_todo",
                        summary=_("INCIDENCIA: contrato sobre el máximo legal vigente"),
                        note=_(
                            "El contrato de %(employee)s quedó en %(current)s hrs/"
                            "semana, por sobre el máximo legal vigente desde hoy "
                            "(%(max)s hrs). No existe un lote de adecuación "
                            "aprobado. Revise y aplique el mecanismo de "
                            "contingencia configurado; documente la distribución "
                            "proporcional y el responsable."
                        )
                        % {
                            "employee": contract.employee_id.name,
                            "current": current_hours,
                            "max": new_max,
                        },
                        user_id=self._get_alert_responsible().id,
                    )
