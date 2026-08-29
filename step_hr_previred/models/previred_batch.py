"""Lote Previred: la traza permanente de cada generación.

Guardar el archivo sin su contexto no sirve para auditar: meses después nadie
puede decir con qué versión del formato, qué alcance y qué motor se produjo.
El lote guarda perfil, versión, fuente, período, compañía, departamentos,
conteos, el hash de cada archivo, el usuario y la fecha.

**No guarda datos personales:** ni RUT, ni nombres, ni importes por persona.
Los hallazgos se guardan por su código, no por su mensaje, porque los mensajes
sí nombran trabajadores.
"""

from odoo import _, api, fields, models

from ..tools import previred


class PreviredBatch(models.Model):
    _name = "step.previred.batch"
    _description = "Lote de exportación Previred"
    _order = "create_date desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)

    user_id = fields.Many2one(
        "res.users", required=True, readonly=True, string="Usuario",
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, string="Empresa",
    )
    date_from = fields.Date(readonly=True, required=True, string="Desde")
    date_to = fields.Date(readonly=True, required=True, string="Hasta")
    period = fields.Char(readonly=True, string="Período")

    profile_id = fields.Many2one(
        "step.previred.profile", readonly=True, string="Perfil",
        ondelete="restrict",
    )
    engine = fields.Char(readonly=True, string="Motor de nómina")
    spec_version = fields.Char(readonly=True, string="Versión del formato")
    spec_source = fields.Char(readonly=True, string="Fuente")

    scope = fields.Selection(
        [("consolidated", "Consolidado"),
         ("departments", "Por departamento"),
         ("both", "Consolidado + departamentos")],
        readonly=True, string="Modo",
    )
    output = fields.Selection(
        [("txt", "TXT oficial"), ("xlsx", "Excel de revisión"),
         ("both", "TXT y Excel")],
        readonly=True, string="Salida",
    )
    department_names = fields.Char(
        readonly=True, string="Departamentos",
        help="Departamentos incluidos. Es configuración, no dato personal.",
    )
    allow_without_department = fields.Boolean(
        readonly=True, string="Permitió trabajadores sin departamento",
    )

    worker_count = fields.Integer(readonly=True, string="Trabajadores")
    principal_count = fields.Integer(readonly=True, string="Líneas principales")
    annex_count = fields.Integer(readonly=True, string="Líneas anexas")
    row_count = fields.Integer(readonly=True, string="Total de líneas")
    department_count = fields.Integer(
        readonly=True, string="N° de departamentos")
    without_department_count = fields.Integer(
        readonly=True, string="Sin departamento")
    error_count = fields.Integer(readonly=True, string="Errores")
    warning_count = fields.Integer(readonly=True, string="Advertencias")

    result = fields.Selection(
        [("ok", "Generado"), ("validated", "Sólo validado"),
         ("blocked", "Bloqueado"), ("error", "Error")],
        required=True, readonly=True, default="ok", string="Resultado",
    )
    issue_codes = fields.Char(
        readonly=True, string="Códigos de hallazgo",
        help="Códigos técnicos de los hallazgos. Los mensajes no se guardan "
             "porque pueden nombrar trabajadores.",
    )
    file_ids = fields.One2many(
        "step.previred.batch.file", "batch_id", readonly=True,
        string="Archivos",
    )

    @api.depends("company_id", "period", "create_date")
    def _compute_display_name(self):
        for batch in self:
            batch.display_name = "Previred %s · %s" % (
                batch.period or "-", batch.company_id.name or "-")

    @api.model
    def record(self, wizard, dataset, scope, output, result="ok",
               file_entries=()):
        """Crea exactamente un registro de auditoría por acción."""
        counters = dataset.counters if dataset else {}
        codes = sorted({issue.code for issue in (dataset.issues if dataset
                                                 else [])})
        batch = self.sudo().create({
            "user_id": self.env.user.id,
            "company_id": wizard.company_id.id,
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
            "period": dataset.period if dataset else "",
            "profile_id": wizard.profile_id.id if wizard.profile_id else False,
            "engine": dataset.engine if dataset else "",
            "spec_version": dataset.spec_version if dataset else "",
            "spec_source": dataset.spec_url if dataset else "",
            "scope": scope,
            "output": output,
            "department_names": ", ".join(
                wizard.department_ids.mapped("name"))[:500] or _("Todos"),
            "allow_without_department": wizard.allow_without_department,
            "worker_count": counters.get("workers", 0),
            "principal_count": counters.get("principal", 0),
            "annex_count": counters.get("annexes", 0),
            "row_count": counters.get("rows", 0),
            "department_count": counters.get("departments", 0),
            "without_department_count": counters.get("without_department", 0),
            "error_count": counters.get("errors", 0),
            "warning_count": counters.get("warnings", 0),
            "result": result,
            "issue_codes": ", ".join(codes)[:500],
        })
        for entry in file_entries:
            self.env["step.previred.batch.file"].sudo().create({
                "batch_id": batch.id,
                "name": entry["filename"],
                "department": entry["department"],
                "worker_count": entry["workers"],
                "row_count": entry["rows"],
                "sha256": entry["sha256"],
                "byte_size": entry.get("size", 0),
                "is_official": entry.get("official", True),
            })
        return batch


class PreviredBatchFile(models.Model):
    """Un archivo del lote, con su hash de control."""

    _name = "step.previred.batch.file"
    _description = "Archivo generado del lote Previred"
    _order = "is_official desc, name"

    batch_id = fields.Many2one(
        "step.previred.batch", required=True, ondelete="cascade",
        readonly=True, index=True,
    )
    name = fields.Char(required=True, readonly=True, string="Archivo")
    department = fields.Char(readonly=True, string="Departamento")
    worker_count = fields.Integer(readonly=True, string="Trabajadores")
    row_count = fields.Integer(readonly=True, string="Líneas")
    sha256 = fields.Char(readonly=True, string="SHA-256")
    byte_size = fields.Integer(readonly=True, string="Bytes")
    is_official = fields.Boolean(
        readonly=True, default=True, string="Cargable en Previred",
        help="Sólo los TXT son cargables. El Excel es un archivo de revisión.",
    )
