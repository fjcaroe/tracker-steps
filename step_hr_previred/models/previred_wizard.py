"""Asistente de exportación Previred.

Separa deliberadamente **validar** de **generar**: se puede revisar el lote y
corregir los datos sin producir todavía un archivo, que es lo que evita que
alguien suba a Previred un archivo que nunca miró.

Todo parámetro se revalida en servidor. El asistente no confía en lo que llega
del cliente: ni la compañía, ni el período, ni los departamentos, ni la
política de «sin departamento».
"""

import base64
import io
import zipfile

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..tools import previred, xlsx_previred
from . import previred_adapter as adapters

GROUP_GENERATE = "step_hr_previred.group_previred_generate"
GROUP_SUMMARY = "step_hr_previred.group_previred_summary"


class PreviredExportWizard(models.TransientModel):
    _name = "step.previred.export.wizard"
    _description = "Exportación Previred por departamento"

    # -- parámetros ---------------------------------------------------------

    company_id = fields.Many2one(
        "res.company", required=True, string="Empresa",
        default=lambda self: self.env.company,
        domain=lambda self: [("id", "in", self.env.companies.ids)],
    )
    date_from = fields.Date(
        required=True, string="Desde",
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(required=True, string="Hasta",
                          default=lambda self: self._default_date_to())
    profile_id = fields.Many2one(
        "step.previred.profile", string="Perfil de formato",
        domain="['|', ('company_ids', '=', False), "
               "('company_ids', 'in', company_id)]",
    )
    scope = fields.Selection(
        [("consolidated", "Consolidado"),
         ("departments", "Por departamento"),
         ("both", "Consolidado + departamentos")],
        default="consolidated", required=True, string="Modo",
    )
    output = fields.Selection(
        [("txt", "TXT oficial"), ("xlsx", "Excel de revisión"),
         ("both", "TXT y Excel")],
        default="txt", required=True, string="Formato",
    )
    department_ids = fields.Many2many(
        "hr.department", string="Departamentos",
        domain="[('company_id', '=', company_id)]",
        help="Vacío = todos los departamentos de la compañía.",
    )
    allow_without_department = fields.Boolean(
        string="Permitir trabajadores sin departamento",
        help="Por defecto un trabajador sin departamento bloquea la "
             "generación. Al marcar esta opción se agrupan en un archivo "
             "«Sin departamento» y la decisión queda registrada en el lote.",
    )
    department_sheets = fields.Boolean(
        string="Una hoja por departamento en el Excel consolidado",
        default=True,
    )
    zip_single = fields.Boolean(
        string="Comprimir aunque sea un solo archivo", default=False,
        help="Un consolidado único se entrega sin comprimir salvo que se "
             "marque esta opción.",
    )

    # -- resultado ----------------------------------------------------------

    state = fields.Selection(
        [("setup", "Parámetros"), ("preview", "Resumen"), ("done", "Archivo")],
        default="setup",
    )
    summary_html = fields.Html(readonly=True, string="Resumen")
    file_data = fields.Binary(readonly=True, attachment=False)
    file_name = fields.Char(readonly=True)
    batch_id = fields.Many2one("step.previred.batch", readonly=True)

    # -- valores por defecto -------------------------------------------------

    @api.model
    def _default_date_to(self):
        import calendar
        today = fields.Date.context_today(self)
        return today.replace(
            day=calendar.monthrange(today.year, today.month)[1])

    @api.onchange("date_from")
    def _onchange_date_from(self):
        """El período Previred es siempre un mes completo."""
        import calendar
        if not self.date_from:
            return
        first = self.date_from.replace(day=1)
        self.date_from = first
        self.date_to = first.replace(
            day=calendar.monthrange(first.year, first.month)[1])
        if self.company_id:
            self.profile_id = self.env[
                "step.previred.profile"].default_for(
                    self.company_id, self.date_from, strict=False)

    @api.onchange("company_id")
    def _onchange_company(self):
        self.department_ids = False
        self.profile_id = self.env["step.previred.profile"].default_for(
            self.company_id, self.date_from, strict=False
        ) if self.company_id else False

    # -- validación de parámetros (siempre en servidor) ----------------------

    def _ensure_export_permission(self):
        """Exige el permiso de generación y acceso real a las liquidaciones.

        Un archivo Previred es corporativo por definición: declara ante las
        instituciones previsionales la nómina completa de la empresa. Quien
        sólo ve a sus subordinados no puede generarlo.

        El nombre no es `_check_access`: en Odoo 18 ese método ya existe en
        `BaseModel` y sobrescribirlo rompería el control de acceso del ORM.
        """
        self.ensure_one()
        if not self.env.user.has_group(GROUP_GENERATE):
            raise AccessError(_(
                "Necesita el permiso «Previred: generar exportaciones» para "
                "producir el archivo."))
        if not self.env.user.has_group("hr_payroll.group_hr_payroll_manager"):
            raise AccessError(_(
                "El archivo Previred contiene la nómina corporativa completa. "
                "Sólo un Administrador de Nómina puede generarlo."))
        payslips = self.env["hr.payslip"]
        try:
            payslips.check_access("read")
        except AttributeError:  # Odoo < 18 nombra el método de otro modo
            payslips.check_access_rights("read")

    def _ensure_corporate_scope(self, profile):
        """Comprueba que las reglas de registro no oculten parte del lote."""
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("date_from", "=", self.date_from),
            ("date_to", "=", self.date_to),
            ("state", "in", list(profile.state_list())),
        ]
        payslips = self.env["hr.payslip"]
        visible = payslips.search_count(domain)
        corporate = payslips.sudo().search_count(domain)
        if visible != corporate:
            raise AccessError(_(
                "Sus reglas de acceso permiten ver %(visible)s de "
                "%(corporate)s liquidaciones elegibles de «%(company)s». "
                "Un Previred parcial no puede presentarse como corporativo.",
                visible=visible, corporate=corporate,
                company=self.company_id.display_name))

    def _validate_parameters(self):
        """Revalida TODO en servidor, venga de donde venga."""
        import calendar
        self.ensure_one()

        if self.company_id not in self.env.companies:
            raise AccessError(_(
                "La compañía «%s» no está entre las compañías habilitadas "
                "para su usuario.", self.company_id.display_name))

        if not self.date_from or not self.date_to:
            raise UserError(_("Indique el período a exportar."))
        if self.date_from.day != 1:
            raise UserError(_(
                "El período Previred es un mes completo: «Desde» debe ser el "
                "día 1 y es el %s.", self.date_from))
        last_day = calendar.monthrange(
            self.date_from.year, self.date_from.month)[1]
        if (self.date_to.year, self.date_to.month, self.date_to.day) != (
                self.date_from.year, self.date_from.month, last_day):
            raise UserError(_(
                "«Hasta» debe ser el último día del mismo mes que «Desde» "
                "(%(expected)s) y es %(found)s.",
                expected=self.date_from.replace(day=last_day),
                found=self.date_to))

        foreign = self.department_ids.filtered(
            lambda department: department.company_id
            and department.company_id != self.company_id)
        if foreign:
            raise UserError(_(
                "Los departamentos %(names)s no pertenecen a la compañía "
                "«%(company)s». Previred no admite mezclar compañías en un "
                "mismo archivo.",
                names=", ".join(foreign.mapped("name")),
                company=self.company_id.display_name))

        profile = self.profile_id or self.env[
            "step.previred.profile"].default_for(
                self.company_id, self.date_from, strict=True)
        if not profile:
            raise UserError(_(
                "No hay un perfil de formato Previred aplicable a «%s». "
                "Configúrelo en Configuración › Previred › Perfiles de "
                "formato.", self.company_id.display_name))
        error = profile.availability_error()
        if error:
            raise UserError(error)
        if profile.company_ids and self.company_id not in profile.company_ids:
            raise UserError(_(
                "El perfil «%(profile)s» no está habilitado para la compañía "
                "«%(company)s».", profile=profile.name,
                company=self.company_id.display_name))
        if not profile.applies_to(self.date_from):
            raise UserError(_(
                "El perfil «%(profile)s» no rige para el período %(period)s. "
                "Seleccione el perfil cuya vigencia cubra ese mes.",
                profile=profile.name,
                period=self.date_from.strftime("%Y-%m")))
        return profile

    # -- construcción del lote ----------------------------------------------

    def _build(self):
        """Construye el dataset canónico UNA vez para esta acción."""
        self.ensure_one()
        self._ensure_export_permission()
        profile = self._validate_parameters()
        self._ensure_corporate_scope(profile)
        adapter = profile.adapter()
        dataset = self.env["step.previred.extractor"].build_dataset(
            company=self.company_id,
            date_from=self.date_from,
            date_to=self.date_to,
            adapter=adapter,
            states=profile.state_list(),
            departments=self.department_ids or None,
            allow_without_department=self.allow_without_department,
            profile_name=profile.name,
            spec_version=profile.spec_version,
            spec_url=profile.source_url,
            spec_effective_from=profile.effective_from,
        )
        self.profile_id = profile
        return dataset

    # -- botones -------------------------------------------------------------

    def action_validate(self):
        """Valida y muestra el resumen SIN producir archivo."""
        self.ensure_one()
        dataset = self._build()
        self.summary_html = self._render_summary(dataset)
        self.state = "preview"
        self.env["step.previred.batch"].record(
            self, dataset, self.scope, self.output,
            result="blocked" if dataset.errors else "validated")
        return self._reopen()

    def action_generate(self):
        """Valida y, si no hay errores, produce el archivo."""
        self.ensure_one()
        dataset = self._build()
        self.summary_html = self._render_summary(dataset)

        if dataset.errors:
            self.state = "preview"
            self.env["step.previred.batch"].record(
                self, dataset, self.scope, self.output, result="blocked")
            # No se lanza una excepción: Odoo revertiría la transacción y con
            # ella desaparecería precisamente el registro de intento bloqueado.
            # El usuario queda en el resumen, sin archivo descargable, y la
            # auditoría conserva el evento.
            self.file_data = False
            self.file_name = False
            return self._reopen()

        if not dataset.records:
            self.env["step.previred.batch"].record(
                self, dataset, self.scope, self.output, result="blocked")
            raise UserError(_(
                "No hay liquidaciones que exportar para «%(company)s» en el "
                "período %(period)s con el alcance seleccionado.",
                company=self.company_id.display_name, period=dataset.period))

        payload, filename, entries = self._render_outputs(dataset)
        batch = self.env["step.previred.batch"].record(
            self, dataset, self.scope, self.output, result="ok",
            file_entries=entries)
        self.write({
            "file_data": base64.b64encode(payload),
            "file_name": filename,
            "state": "done",
            "batch_id": batch.id,
        })
        return self._reopen()

    def action_back(self):
        self.ensure_one()
        self.state = "setup"
        return self._reopen()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    # -- salidas -------------------------------------------------------------

    def _txt_entry(self, records, department_label, department_code, dataset):
        text = previred.render_records(records)
        data = previred.txt_bytes(text)
        filename = previred.txt_filename(
            dataset.company_vat, dataset.period, department_code)
        return {
            "filename": filename,
            "department": department_label,
            "workers": len(records),
            "rows": sum(len(record.rows) for record in records),
            "sha256": previred.sha256_hex(data),
            "size": len(data),
            "official": True,
            "data": data,
        }

    def _xlsx_entry(self, dataset, records, department_label, department_code,
                    scope_label, per_department_sheets, file_entries):
        stream = io.BytesIO()
        xlsx_previred.build_workbook(
            stream, dataset, scope_label=scope_label,
            per_department_sheets=per_department_sheets, records=records,
            file_entries=file_entries)
        data = stream.getvalue()
        filename = previred.xlsx_filename(
            dataset.company_vat, dataset.period, department_code)
        return {
            "filename": filename,
            "department": department_label,
            "workers": len(records),
            "rows": sum(len(record.rows) for record in records),
            "sha256": previred.sha256_hex(data),
            "size": len(data),
            "official": False,
            "data": data,
        }

    def _render_outputs(self, dataset):
        """Genera los archivos pedidos a partir del dataset ya construido.

        Nada aquí vuelve a consultar la base: todas las salidas son
        particiones del mismo lote.
        """
        self.ensure_one()
        want_txt = self.output in ("txt", "both")
        want_xlsx = self.output in ("xlsx", "both")
        want_consolidated = self.scope in ("consolidated", "both")
        want_departments = self.scope in ("departments", "both")

        consolidated_records = dataset.sorted_records()
        grouped = dataset.by_department()
        department_codes = {
            department_id: code
            for department_id, _label, code in dataset.departments()
        }

        txt_entries = []
        if want_txt and want_consolidated:
            txt_entries.append(self._txt_entry(
                consolidated_records, _("Consolidado"), None, dataset))
        if want_txt and want_departments:
            for department_id, label, code in dataset.departments():
                txt_entries.append(self._txt_entry(
                    grouped[department_id], label, code, dataset))

        entries = list(txt_entries)

        if want_xlsx and want_consolidated:
            entries.append(self._xlsx_entry(
                dataset, consolidated_records, _("Consolidado"), None,
                _("Consolidado"), self.department_sheets, txt_entries))
        if want_xlsx and want_departments:
            for department_id, label, code in dataset.departments():
                entries.append(self._xlsx_entry(
                    dataset, grouped[department_id], label, code,
                    _("Departamento: %s", label), False,
                    [entry for entry in txt_entries
                     if entry["department"] == label]))

        if not entries:
            raise UserError(_("La combinación de modo y formato no produce "
                              "ningún archivo."))

        if len(entries) == 1 and not self.zip_single:
            entry = entries[0]
            return entry["data"], entry["filename"], entries

        manifest = previred.build_manifest(
            [entry for entry in entries if entry["official"]], dataset)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry in entries:
                archive.writestr(entry["filename"], entry["data"])
            archive.writestr(previred.MANIFEST_NAME,
                             previred.txt_bytes(manifest))
        return (stream.getvalue(),
                previred.zip_filename(dataset.company_vat, dataset.period),
                entries)

    # -- resumen -------------------------------------------------------------

    def _render_summary(self, dataset):
        """Resumen previo. Los mensajes con datos de personas sólo se muestran
        a quien tiene el permiso de consulta del resumen."""
        self.ensure_one()
        counters = dataset.counters
        may_see_detail = self.env.user.has_group(GROUP_SUMMARY) \
            or self.env.user.has_group(GROUP_GENERATE)

        rows = [
            (_("Empresa"), dataset.company_name),
            (_("Período"), dataset.period),
            (_("Motor de nómina"), dataset.engine),
            (_("Formato"), "%s v%s (rige desde %s)"
             % (previred.SPEC_NAME, dataset.spec_version,
                dataset.spec_effective_from)),
            (_("Estados exportados"), ", ".join(dataset.eligible_states)),
            (_("Liquidaciones elegibles"), dataset.eligible_payslip_count),
            (_("Trabajadores"), counters["workers"]),
            (_("Líneas principales"), counters["principal"]),
            (_("Líneas anexas"), counters["annexes"]),
            (_("Total de líneas"), counters["rows"]),
            (_("Departamentos"), counters["departments"]),
            (_("Sin departamento"), counters["without_department"]),
            (_("Errores"), counters["errors"]),
            (_("Advertencias"), counters["warnings"]),
        ]
        parts = ["<div class='o_previred_summary'>"]
        parts.append(
            "<div class='alert alert-info' role='status'>"
            "Previred sólo admite archivos <strong>TXT, CSV o ZIP</strong>. "
            "El Excel que genera este asistente es un <strong>archivo de "
            "revisión</strong> y no debe cargarse en Previred.</div>")
        parts.append("<table class='table table-sm'><tbody>")
        for label, value in rows:
            parts.append("<tr><th style='width:38%%'>%s</th><td>%s</td></tr>"
                         % (label, value))
        parts.append("</tbody></table>")

        if dataset.departments():
            parts.append("<h5>%s</h5><table class='table table-sm'><tbody>"
                         % _("Trabajadores por departamento"))
            grouped = dataset.by_department()
            for department_id, label, _code in dataset.departments():
                parts.append("<tr><th style='width:38%%'>%s</th><td>%d</td>"
                             "</tr>" % (label, len(grouped[department_id])))
            parts.append("</tbody></table>")

        for severity, title, css in (
                (previred.SEVERITY_ERROR, _("Errores"), "danger"),
                (previred.SEVERITY_WARNING, _("Advertencias"), "warning")):
            issues = [issue for issue in dataset.issues
                      if issue.severity == severity]
            if not issues:
                continue
            parts.append("<h5>%s (%d)</h5>" % (title, len(issues)))
            if not may_see_detail:
                parts.append(
                    "<div class='alert alert-%s'>%s</div>"
                    % (css, _("No tiene permiso para ver el detalle por "
                              "trabajador.")))
                continue
            parts.append("<ul class='text-%s'>" % css)
            for issue in issues[:60]:
                parts.append("<li>%s</li>" % issue.message)
            if len(issues) > 60:
                parts.append("<li>%s</li>" % _("… y %d más.",
                                               len(issues) - 60))
            parts.append("</ul>")
        parts.append("</div>")
        return "".join(parts)
