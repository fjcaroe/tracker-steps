import calendar
import hmac as hmac_lib
import time
from datetime import date
from urllib.parse import urlencode

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import hmac as odoo_hmac

from ..tools import dt_book

MONTHS = [
    ("1", "Enero"), ("2", "Febrero"), ("3", "Marzo"), ("4", "Abril"),
    ("5", "Mayo"), ("6", "Junio"), ("7", "Julio"), ("8", "Agosto"),
    ("9", "Septiembre"), ("10", "Octubre"), ("11", "Noviembre"),
    ("12", "Diciembre"),
]

MONTH_NAMES = dict(MONTHS)

#: Grupos que habilitan el libro corporativo y sus cuatro salidas: el
#: Administrador de Nómina —que tiene acceso real a todas las liquidaciones— o
#: el grupo Steps de exportación completa. Se comprueban los dos y no sólo la
#: implicación entre ellos, para que el permiso no dependa de que una
#: implicación se haya podido escribir sobre un módulo ajeno.
FULL_GROUP = "step_hr_remuneration_book.group_remuneration_book_full"
PAYROLL_MANAGER_GROUP = "hr_payroll.group_hr_payroll_manager"

#: Grupo mínimo para el reporte parcial: sólo lo que las reglas de registro
#: dejan ver a ese usuario, y explícitamente rotulado como parcial.
PARTIAL_GROUP = "hr_payroll.group_hr_payroll_user"

#: Ámbito y vida del token de descarga. Corto a propósito: el enlace se abre
#: inmediatamente después de pulsar el botón.
TOKEN_SCOPE = "step_hr_remuneration_book.download"
TOKEN_TTL = 300


class HrLibroRemuneracionesWizard(models.TransientModel):
    _name = "step.hr.remuneration.book.wizard"
    _description = "Libro de Remuneraciones Steps"

    mode = fields.Selection(
        [
            ("full", "Libro de Remuneraciones (empresa completa)"),
            ("partial", "Reporte parcial de remuneraciones"),
        ],
        required=True, default="full", string="Tipo de informe",
    )
    company_id = fields.Many2one(
        "res.company", required=True, string="Empresa",
        default=lambda self: self.env.company,
    )
    month = fields.Selection(
        MONTHS, required=True, string="Mes de remuneraciones",
        default=lambda self: str(fields.Date.context_today(self).month),
    )
    year = fields.Integer(
        required=True, string="Año",
        default=lambda self: fields.Date.context_today(self).year,
    )
    group_by = fields.Selection(
        [("department", "Departamento")],
        required=True, default="department", string="Agrupar por",
    )
    date_from = fields.Date(compute="_compute_period", string="Desde")
    date_to = fields.Date(compute="_compute_period", string="Hasta")
    period_label = fields.Char(compute="_compute_period", string="Período")
    profile_id = fields.Many2one(
        "step.remuneration.book.profile", readonly=True,
        string="Perfil de mapeo",
    )
    profile_origin = fields.Selection(
        [
            ("assigned", "Asignado"),
            ("detected", "Detectado"),
            ("unconfirmed", "Sin confirmar"),
        ],
        default="unconfirmed", readonly=True, string="Origen del perfil",
    )
    scope_label = fields.Char(
        compute="_compute_scope", string="Alcance", readonly=True,
    )
    official_csv_available = fields.Boolean(
        compute="_compute_scope", string="Archivo oficial disponible",
    )
    official_csv_message = fields.Char(compute="_compute_scope", readonly=True)
    preview_html = fields.Html(
        string="Síntesis de control", readonly=True, sanitize=True,
    )
    preview_blocked = fields.Boolean(
        readonly=True, default=False,
        help="Verdadero cuando la última revisión encontró errores que "
             "impiden generar el informe.",
    )
    preview_done = fields.Boolean(readonly=True, default=False)

    # -- período ------------------------------------------------------------

    @api.depends("month", "year")
    def _compute_period(self):
        for wizard in self:
            month = int(wizard.month or 0)
            year = wizard.year or 0
            if not month or not year:
                wizard.date_from = wizard.date_to = False
                wizard.period_label = ""
                continue
            last_day = calendar.monthrange(year, month)[1]
            wizard.date_from = date(year, month, 1)
            wizard.date_to = date(year, month, last_day)
            wizard.period_label = "%s %s" % (MONTH_NAMES[str(month)], year)

    @api.constrains("year")
    def _check_year(self):
        for wizard in self:
            if not 2000 <= (wizard.year or 0) <= 2100:
                raise UserError(_("Indique un año entre 2000 y 2100."))

    def _check_period_is_a_calendar_month(self):
        """El libro es mensual: nunca un rango arbitrario.

        Se comprueba aquí y no sólo en el controlador para que la regla valga
        igual desde el asistente, desde una prueba y desde un informe.
        """
        self.ensure_one()
        month, year = int(self.month or 0), self.year or 0
        if not month or not year:
            raise UserError(_("Indique mes y año."))
        last_day = calendar.monthrange(year, month)[1]
        if (self.date_from != date(year, month, 1)
                or self.date_to != date(year, month, last_day)):
            raise UserError(_(
                "El período debe ser un mes calendario completo."))

    # -- alcance y disponibilidad -------------------------------------------

    @api.depends("mode", "company_id")
    def _compute_scope(self):
        extractor = self.env["step.remuneration.book.extractor"]
        module, label = extractor.official_csv_source()
        for wizard in self:
            scope = wizard._scope()
            wizard.scope_label = dt_book.SCOPE_LABELS[scope]
            if scope != dt_book.SCOPE_FULL:
                wizard.official_csv_available = False
                wizard.official_csv_message = _(
                    "El archivo oficial DT sólo se emite con alcance de "
                    "empresa completa.")
            elif not module:
                wizard.official_csv_available = False
                wizard.official_csv_message = _(
                    "No hay una fuente oficial DT instalada en esta base.")
            else:
                wizard.official_csv_available = True
                wizard.official_csv_message = _(
                    "Generado por la fuente oficial instalada: %s.", label)

    @api.model
    def user_has_full_access(self):
        """Permiso para el libro corporativo, comprobado sin ambigüedad."""
        user = self.env.user
        return (user.has_group(FULL_GROUP)
                or user.has_group(PAYROLL_MANAGER_GROUP))

    def _scope(self):
        self.ensure_one()
        return (dt_book.SCOPE_FULL if self.mode == "full"
                else dt_book.SCOPE_PARTIAL)

    # -- acceso --------------------------------------------------------------

    def _step_check_access(self):
        """Política inequívoca de permisos.

        El libro corporativo, sus cuatro salidas y la auditoría exigen el grupo
        de exportación completa. El reporte parcial existe como acción
        separada, rotulada como parcial, y nunca ofrece el CSV oficial.
        """
        self.ensure_one()
        if self.mode == "full":
            if not self.user_has_full_access():
                raise UserError(_(
                    "El Libro de Remuneraciones corporativo sólo puede "
                    "generarlo un Administrador de Nómina o un usuario del "
                    "grupo de exportación completa."))
        elif not self.env.user.has_group(PARTIAL_GROUP):
            raise UserError(_(
                "Sólo el personal autorizado de Nómina puede generar informes "
                "de remuneraciones."))
        if self.company_id not in self.env.companies:
            raise UserError(_("No tiene acceso a la empresa seleccionada."))

    # -- datos --------------------------------------------------------------

    def _payslip_domain(self):
        self.ensure_one()
        return [
            ("date_from", ">=", self.date_from),
            ("date_to", "<=", self.date_to),
            ("company_id", "=", self.company_id.id),
            ("state", "in", ["done", "paid"]),
        ]

    def _payslips(self):
        """Liquidaciones Hechas o Pagadas del mes y la empresa seleccionados."""
        self.ensure_one()
        self._step_check_access()
        self._check_period_is_a_calendar_month()
        Payslip = self.env["hr.payslip"].with_context(
            allowed_company_ids=[self.company_id.id]
        )
        payslips = Payslip.search(
            self._payslip_domain(), order="employee_id, date_from, id")
        if self.mode == "full":
            # Un libro corporativo incompleto es peor que ningún libro: si las
            # reglas de registro esconden liquidaciones a este usuario, se
            # bloquea en vez de entregar una parte que parece el total.
            visible = len(payslips)
            total = Payslip.sudo().search_count(self._payslip_domain())
            if visible != total:
                raise UserError(_(
                    "Su usuario sólo ve %(visible)s de las %(total)s "
                    "liquidaciones de %(company)s en %(period)s. El Libro de "
                    "Remuneraciones corporativo exige acceso a todas: use el "
                    "«Reporte parcial de remuneraciones» o solicite el "
                    "permiso correspondiente.",
                    visible=visible, total=total,
                    company=self.company_id.name, period=self.period_label))
        if not payslips:
            raise UserError(_(
                "No se encontraron liquidaciones en estado Hecho o Pagado para "
                "%(period)s en %(company)s.",
                period=self.period_label, company=self.company_id.name,
            ))
        foreign = payslips.filtered(lambda p: p.company_id != self.company_id)
        if foreign:
            raise UserError(_(
                "Se detectaron liquidaciones de otra empresa en el resultado. "
                "El informe se detiene por seguridad."
            ))
        return payslips

    def _resolve_profile(self, payslips):
        """Resolución determinística, por compañía y por período."""
        self.ensure_one()
        extractor = self.env["step.remuneration.book.extractor"]
        present = extractor.payslip_rule_codes(payslips)
        profile, origin, issues = self.env[
            "step.remuneration.book.profile"
        ].resolve_for(self.company_id, present)
        self.profile_id = profile
        self.profile_origin = origin
        return profile, origin, issues

    def _tolerance(self):
        """Tolerancia efectiva. `0` significa estricta, no «por defecto»."""
        self.ensure_one()
        tolerance = self.company_id.remuneration_book_tolerance
        if tolerance is None or tolerance is False:
            return dt_book.DEFAULT_TOLERANCE
        return int(tolerance)

    def build_dataset(self):
        """Dataset único que consumen Excel, PDF y previsualización.

        Se construye UNA vez por acción del usuario: el botón sólo valida y
        devuelve la acción; el dataset lo arma la petición que produce el
        archivo.
        """
        self.ensure_one()
        payslips = self._payslips()
        profile, origin, profile_issues = self._resolve_profile(payslips)
        if profile_issues or not profile:
            return dt_book.build_dataset(
                [], tolerance=self._tolerance(), issues=profile_issues,
                company_name=self.company_id.name or "",
                company_vat=self.company_id.vat or "",
                period_label=self.period_label,
                date_from=self.date_from, date_to=self.date_to,
                source=profile.name if profile else _("Sin perfil"),
                scope=self._scope(), profile_origin=origin,
                generated_at=fields.Datetime.to_string(fields.Datetime.now()),
            )
        extractor = self.env["step.remuneration.book.extractor"]
        lines, issues = extractor.extract_lines(payslips, profile)
        return dt_book.build_dataset(
            lines,
            tolerance=self._tolerance(),
            issues=issues,
            company_name=self.company_id.name or "",
            company_vat=self.company_id.vat or "",
            period_label=self.period_label,
            date_from=self.date_from,
            date_to=self.date_to,
            source=profile.name,
            scope=self._scope(),
            profile_origin=origin,
            generated_at=fields.Datetime.to_string(fields.Datetime.now()),
        )

    def generate(self, output):
        """Construye el dataset y registra exactamente UNA línea de auditoría.

        Es el único punto por el que pasan Excel, PDF, fichas y
        previsualización, de modo que una acción del usuario no puede producir
        dos datasets ni dos registros de auditoría.
        """
        self.ensure_one()
        Log = self.env["step.remuneration.book.log"]
        try:
            dataset = self.build_dataset()
        except UserError as error:
            Log.record(
                self, output, result="blocked", detail="user_error",
                user=self.env.user)
            raise
        if dataset.errors:
            Log.record(
                self, output, result="blocked", dataset=dataset,
                detail=dataset.errors[0].code, user=self.env.user)
            raise UserError(_(
                "El informe no puede generarse todavía:\n\n%s",
                "\n".join("• %s" % issue.message for issue in dataset.errors[:10]),
            ))
        Log.record(self, output, dataset=dataset, user=self.env.user)
        return dataset

    # -- previsualización ---------------------------------------------------

    @api.onchange("company_id", "month", "year")
    def _onchange_period(self):
        """La síntesis mostrada deja de ser válida al cambiar el período."""
        self.preview_html = False
        self.preview_done = False
        self.preview_blocked = False
        if self.company_id:
            assigned = self.company_id.remuneration_book_profile_id
            self.profile_id = assigned
            self.profile_origin = "assigned" if assigned else "unconfirmed"

    def _render_preview(self, dataset, blocking_message=""):
        """Síntesis renderizada con QWeb.

        Todo valor —nombre de empresa, perfil, fuente, mensajes de error— se
        escapa en la plantilla. Nunca se concatena HTML a mano.
        """
        self.ensure_one()
        return self.env["ir.qweb"]._render(
            "step_hr_remuneration_book.preview_synthesis",
            {
                "dataset": dataset,
                "wizard": self,
                "counters": dataset.counters if dataset else {},
                "blocking_message": blocking_message,
                "errors": dataset.errors[:10] if dataset else [],
                "warnings": dataset.warnings[:15] if dataset else [],
                "extra_warnings": max(
                    len(dataset.warnings) - 15, 0) if dataset else 0,
            },
        )

    def action_refresh_preview(self):
        """Recalcula la síntesis sin cerrar el asistente."""
        self.ensure_one()
        Log = self.env["step.remuneration.book.log"]
        try:
            dataset = self.build_dataset()
        except UserError as error:
            message = error.args[0] if error.args else ""
            self.preview_html = self._render_preview(None, message)
            self.preview_blocked = True
            self.preview_done = True
            Log.record(self, "preview", result="blocked",
                       detail="user_error", user=self.env.user)
            return self._reopen()
        self.preview_html = self._render_preview(dataset)
        self.preview_blocked = bool(dataset.errors)
        self.preview_done = True
        Log.record(
            self, "preview",
            result="blocked" if dataset.errors else "ok",
            dataset=dataset, user=self.env.user)
        return self._reopen()

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": (_("Libro de Remuneraciones") if self.mode == "full"
                     else _("Reporte parcial de remuneraciones")),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # -- salidas ------------------------------------------------------------

    def _token_payload(self, output, expires_at):
        self.ensure_one()
        return "%s|%s|%s|%s|%s|%s" % (
            self.id, output, self.env.uid, self.company_id.id,
            self.date_from.isoformat(), expires_at,
        )

    def _download_token(self, output, expires_at):
        return odoo_hmac(
            self.env(su=True), TOKEN_SCOPE,
            self._token_payload(output, expires_at))

    @api.model
    def check_download_token(self, wizard, output, token, expires_at):
        """Valida el token de descarga: firma, vigencia y titular."""
        try:
            expires_at = int(expires_at)
        except (TypeError, ValueError):
            return False
        if expires_at < int(time.time()):
            return False
        expected = wizard._download_token(output, expires_at)
        return hmac_lib.compare_digest(expected, token or "")

    def _download_url(self, route, output):
        """Enlace firmado y de vida corta, ligado al asistente y al usuario.

        No se confía en parámetros GET manipulables: van también las fechas y
        la empresa, pero sólo como comprobación cruzada contra el asistente que
        el usuario acaba de validar.
        """
        self.ensure_one()
        self._step_check_access()
        self._check_period_is_a_calendar_month()
        expires_at = int(time.time()) + TOKEN_TTL
        query = urlencode({
            "wizard_id": self.id,
            "output": output,
            "exp": expires_at,
            "token": self._download_token(output, expires_at),
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "company_id": self.company_id.id,
        })
        return {
            "type": "ir.actions.act_url",
            "url": "%s?%s" % (route, query),
            "target": "self",
        }

    def _check_ready(self, output):
        """Comprobación barata previa: no construye el dataset.

        El dataset lo construye una sola vez la petición que genera el archivo.
        Aquí sólo se verifica que la salida esté habilitada.
        """
        self.ensure_one()
        self._step_check_access()
        if self.preview_done and self.preview_blocked:
            raise UserError(_(
                "La última revisión encontró errores que impiden generar el "
                "informe. Corrija los puntos indicados en la síntesis y vuelva "
                "a revisar."))
        if output == "csv" and not self.official_csv_available:
            raise UserError(self.official_csv_message)

    def action_download_xlsx(self):
        self._check_ready("xlsx")
        return self._download_url(
            "/step/payroll/remuneration-book/xlsx", "xlsx")

    def action_download_official_csv(self):
        self._check_ready("csv")
        return self._download_url(
            "/step/payroll/remuneration-book/official-csv", "csv")

    def action_download_pdf(self):
        self._check_ready("pdf")
        return self.env.ref(
            "step_hr_remuneration_book.action_report_consolidated_book"
        ).report_action(self)

    def action_download_employee_sheets(self):
        self._check_ready("sheets")
        return self.env.ref(
            "step_hr_remuneration_book.action_report_employee_sheets"
        ).report_action(self)
