# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html_escape

# Lista blanca explícita de variables permitidas en las plantillas.
# No se acepta ninguna expresión Python arbitraria: el motor de render
# sólo reemplaza estos tokens exactos, nada más.
TEMPLATE_VARIABLES = {
    "empleador.nombre": lambda c: c.company_id.name or "",
    "empleador.rut": lambda c: c.company_id.vat or "",
    "empleador.direccion": lambda c: c.company_id.partner_id.contact_address or "",
    "trabajador.nombre": lambda c: c.employee_id.name or "",
    "trabajador.rut": lambda c: c.employee_id.identification_id or "",
    "trabajador.nacionalidad": lambda c: c.employee_id.country_id.name or "",
    "contrato.modalidad": lambda c: dict(
        c._fields["labor_modality"].selection
    ).get(c.labor_modality, ""),
    "contrato.cargo": lambda c: c.job_id.name or "",
    "contrato.fundo": lambda c: c.fundo_id.name or "",
    "contrato.fecha_inicio": lambda c: c.date_start and c.date_start.strftime("%d/%m/%Y") or "",
    "contrato.fecha_termino": lambda c: c.date_end and c.date_end.strftime("%d/%m/%Y") or "",
    "contrato.fecha_celebracion": lambda c: c.date_signature and c.date_signature.strftime("%d/%m/%Y") or "",
    "contrato.comuna_celebracion": lambda c: c.commune_signature_id.name or "",
    "contrato.sueldo_base": lambda c: "{:,.0f}".format(c.wage or 0).replace(",", "."),
    "contrato.jornada_semanal": lambda c: str(c.resource_calendar_id.hours_per_week or 0),
    "contrato.jornada_maxima_legal": lambda c: str(c.max_weekly_hours_legal or 0),
    "contrato.lugar_trabajo": lambda c: ", ".join(
        filter(
            None,
            [
                c.work_street and f"{c.work_street} {c.work_number or ''}".strip(),
                c.work_commune_id.name,
            ],
        )
    ),
}


class HrLaborTemplate(models.Model):
    """Plantilla laboral versionada y multiempresa (contrato, carta de
    aviso o finiquito). Editar la plantilla NUNCA cambia un documento ya
    emitido: hr.labor.document guarda un snapshot congelado."""

    _name = "hr.labor.template"
    _description = "Plantilla laboral (contrato / aviso / finiquito)"
    _inherit = ["mail.thread"]
    _order = "document_type, modality, version desc"

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    document_type = fields.Selection(
        [
            ("contract", "Contrato"),
            ("notice", "Carta de aviso"),
            ("severance", "Finiquito"),
        ],
        required=True,
        tracking=True,
    )
    modality = fields.Selection(
        [
            ("temporada", "Temporada / faena transitoria"),
            ("trato", "A trato"),
            ("plazo_fijo", "Plazo fijo"),
            ("permanente", "Agrícola permanente / indefinido"),
        ],
        help="Vacío si el tipo de documento no depende de la modalidad "
        "(cartas de aviso y finiquitos no suelen distinguir modalidad).",
    )
    version = fields.Integer(default=1, readonly=True)
    date_from = fields.Date(string="Vigente desde", required=True, tracking=True)
    date_to = fields.Date(string="Vigente hasta", tracking=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("validated", "Validada"), ("obsolete", "Obsoleta")],
        default="draft",
        tracking=True,
    )
    lang = fields.Selection(lambda self: self.env["res.lang"].get_installed(), default="es_CL")
    body_html = fields.Html(
        string="Cuerpo del documento",
        sanitize=True,
        sanitize_tags=True,
        sanitize_attributes=True,
        help="Use únicamente variables de la lista blanca, ej: "
        "{{trabajador.nombre}}. No se admite código Python.",
    )
    approval_responsible_id = fields.Many2one(
        "res.users", string="Responsable de aprobación", tracking=True
    )
    legal_notes = fields.Text(string="Notas legales")
    sequence_code = fields.Char(
        string="Código de secuencia",
        help="Prefijo de numeración por compañía y tipo, ej: CONT-TEMP.",
    )

    def action_validate(self):
        for tpl in self:
            if not tpl.body_html:
                raise UserError(_("La plantilla no tiene cuerpo de documento."))
            tpl.state = "validated"

    def action_obsolete(self):
        self.write({"state": "obsolete"})

    def action_new_version(self):
        self.ensure_one()
        new = self.copy(
            {
                "version": self.version + 1,
                "state": "draft",
                "date_from": fields.Date.context_today(self),
                "date_to": False,
            }
        )
        self.state = "obsolete"
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.labor.template",
            "res_id": new.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def _available_variables(self):
        return sorted(TEMPLATE_VARIABLES.keys())

    def _find_missing_variables(self):
        self.ensure_one()
        used = set(re.findall(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}", self.body_html or ""))
        unknown = used - set(TEMPLATE_VARIABLES.keys())
        return sorted(unknown)

    def action_check_variables(self):
        self.ensure_one()
        missing = self._find_missing_variables()
        if missing:
            raise UserError(
                _(
                    "Variables no reconocidas (no están en la lista blanca): %s"
                )
                % ", ".join(missing)
            )
        return True

    def render(self, contract):
        """Renderiza el cuerpo reemplazando SÓLO tokens de la lista
        blanca. Nunca evalúa código arbitrario."""
        self.ensure_one()
        unknown = self._find_missing_variables()
        if unknown:
            raise UserError(
                _("La plantilla usa variables no permitidas: %s") % ", ".join(unknown)
            )
        html = self.body_html or ""

        def _replace(match):
            token = match.group(1)
            getter = TEMPLATE_VARIABLES.get(token)
            value = getter(contract) if getter else ""
            return html_escape(str(value))

        return re.sub(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}", _replace, html)

    def action_preview(self):
        self.ensure_one()
        sample_contract = self.env["hr.contract"].search(
            [("company_id", "=", self.company_id.id)], limit=1
        )
        if not sample_contract:
            raise UserError(_("No hay ningún contrato en esta compañía para previsualizar."))
        rendered = self.render(sample_contract)
        return {
            "type": "ir.actions.act_window",
            "name": _("Vista previa"),
            "res_model": "hr.labor.template.preview",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_template_id": self.id,
                "default_preview_html": rendered,
            },
        }
