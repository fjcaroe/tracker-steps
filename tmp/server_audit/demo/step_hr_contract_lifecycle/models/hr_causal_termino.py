# -*- coding: utf-8 -*-
from odoo import fields, models


class HrCausalTermino(models.Model):
    """Extiende el maestro de causales de término (l10n_cl_hr) con los
    datos que exige la carga masiva de avisos/finiquitos a la DT y con las
    banderas de cálculo de haberes de finiquito.

    No se duplica el maestro: ya existe ``hr.causal.termino`` (código +
    nombre) con 21 causales cargadas; sólo se agregan los campos que
    faltan.
    """

    _inherit = "hr.causal.termino"

    articulo = fields.Char(
        string="Artículo/inciso",
        help="Ej: Art.159N1 — tal como exige el instructivo de la DT "
        "(columna ArticuloCausal / CodigoTipoCausal).",
    )
    dt_codigo_causal = fields.Integer(
        string="Código DT",
        help="Código numérico de la tabla 'Causales de Despido' del "
        "instructivo de carta de aviso de la DT.",
    )
    description_legal = fields.Text(string="Descripción legal")
    active = fields.Boolean(default=True)
    date_from = fields.Date(
        string="Vigente desde",
        help="Vigencia de esta causal/redacción. Permite versionar el "
        "texto legal sin perder el histórico de finiquitos ya emitidos.",
    )
    date_to = fields.Date(string="Vigente hasta")
    requires_certificate = fields.Boolean(
        string="Requiere certificado/adjunto",
        help="Ej: Art. 163 bis exige adjuntar certificado del "
        "procedimiento concursal antes de notificar el aviso.",
    )
    notice_deadline_days = fields.Integer(
        string="Plazo de aviso (días corridos)",
        default=3,
        help="Días corridos desde el término para notificar la carta de "
        "aviso. Valor por defecto conservador (3 días); revisar y "
        "ajustar por causal contra el instructivo DT vigente antes de "
        "usar en producción — el plazo real varía según el artículo "
        "invocado (ej. 6 días para algunas causales del art. 160).",
    )
    applies_ias_anual = fields.Boolean(
        string="Aplica IAS anual (art. 163)",
        help="Indemnización por años de servicio.",
    )
    applies_ias_mensual = fields.Boolean(
        string="Aplica IAS mensual (art. 159 N°5)",
        help="Indemnización por meses de servicio, contratos de temporada.",
    )
    applies_mes_aviso = fields.Boolean(
        string="Aplica indemnización sustitutiva de aviso previo",
    )
