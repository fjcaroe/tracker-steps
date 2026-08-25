# -*- coding: utf-8 -*-
from odoo import fields, models


class StepHrTerminationCause(models.Model):
    """Maestro propio y estable de causales de término, independiente de
    cualquier motor de nómina. No hereda ``hr.causal.termino``
    (l10n_cl_hr) ni ``hr.causal.contract.end`` (SimpleDigital) porque
    ninguno de los dos existe garantizado en todos los ambientes: los
    adaptadores copian de forma idempotente sus causales existentes
    hacia este modelo (ver ``origin_model``/``origin_id``), sin borrar
    ni modificar el maestro de origen.
    """

    _name = "step.hr.termination.cause"
    _description = "Causal de término (núcleo, independiente de motor)"
    _inherit = ["mail.thread"]
    _order = "code"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string="Código interno", required=True, tracking=True)
    dt_code = fields.Char(string="Código DT", tracking=True)
    articulo = fields.Char(string="Artículo/inciso", tracking=True)
    description_legal = fields.Text(string="Descripción legal")
    date_from = fields.Date(string="Vigente desde")
    date_to = fields.Date(string="Vigente hasta")
    requires_certificate = fields.Boolean(string="Requiere certificado/adjunto")
    notice_deadline_days = fields.Integer(
        string="Plazo de aviso (días corridos)",
        default=3,
        help="Valor por defecto conservador; ajustar por causal según el "
        "instructivo DT vigente.",
    )
    applies_ias_anual = fields.Boolean(string="Aplica IAS anual (art. 163)")
    applies_ias_mensual = fields.Boolean(string="Aplica IAS mensual (art. 159 N°5)")
    applies_mes_aviso = fields.Boolean(string="Aplica indemnización sustitutiva de aviso previo")
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        help="Vacío = disponible para todas las compañías.",
    )
    active = fields.Boolean(default=True)

    # -- Trazabilidad de origen (migración idempotente desde adaptadores) --
    origin_model = fields.Char(
        string="Modelo de origen",
        readonly=True,
        help="Ej: 'hr.causal.termino' o 'hr.causal.contract.end', si esta "
        "causal fue copiada desde el maestro de un adaptador.",
    )
    origin_id = fields.Integer(string="ID de origen", readonly=True)

    _sql_constraints = [
        (
            "code_uniq",
            "unique(code)",
            "El código interno de la causal debe ser único.",
        ),
        (
            "origin_uniq",
            "unique(origin_model, origin_id)",
            "Esta causal de origen ya fue migrada (evita duplicados en "
            "reejecuciones de la migración).",
        ),
    ]
