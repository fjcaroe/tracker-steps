from odoo import api, fields, models

from ..tools import dt_book


class RemunerationBookLog(models.Model):
    """Auditoría mínima de exportaciones.

    Registra quién exportó qué y con qué resultado. No guarda montos por
    persona, ni RUT, ni nombres: sólo conteos agregados.
    """

    _name = "step.remuneration.book.log"
    _description = "Auditoría de exportaciones del Libro de Remuneraciones"
    _order = "create_date desc"
    _rec_name = "output"

    user_id = fields.Many2one(
        "res.users", required=True, readonly=True, string="Usuario",
        help="Usuario que inició la acción, aunque una operación interna haya "
             "usado elevación controlada.",
    )
    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, string="Empresa"
    )
    date_from = fields.Date(readonly=True, string="Desde")
    date_to = fields.Date(readonly=True, string="Hasta")
    output = fields.Selection(
        [
            ("xlsx", "Libro consolidado Excel"),
            ("pdf", "Libro consolidado PDF"),
            ("csv", "Archivo oficial DT"),
            ("sheets", "Fichas detalladas por trabajador"),
            ("preview", "Previsualización"),
        ],
        required=True, readonly=True, string="Salida",
    )
    scope = fields.Selection(
        [
            (dt_book.SCOPE_FULL, "Empresa completa"),
            (dt_book.SCOPE_PARTIAL, "Parcial"),
        ],
        readonly=True, string="Alcance",
    )
    result = fields.Selection(
        [("ok", "Generado"), ("blocked", "Bloqueado"), ("error", "Error")],
        required=True, readonly=True, default="ok", string="Resultado",
    )
    profile_id = fields.Many2one(
        "step.remuneration.book.profile", readonly=True, string="Perfil"
    )
    line_count = fields.Integer(readonly=True, string="Líneas")
    payslip_count = fields.Integer(readonly=True, string="Liquidaciones")
    warning_count = fields.Integer(readonly=True, string="Advertencias")
    detail = fields.Char(readonly=True, string="Detalle")

    @api.model
    def record(self, wizard, output, result="ok", dataset=None, detail="",
               user=None):
        """Crea exactamente un registro de auditoría.

        `detail` guarda el CÓDIGO del hallazgo, nunca su mensaje: los mensajes
        pueden mencionar identificadores de liquidación y no tienen por qué
        vivir en un registro permanente.
        """
        counters = (dataset.counters if dataset else {}) or {}
        return self.sudo().create({
            "user_id": (user or self.env.user).id,
            "company_id": wizard.company_id.id,
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
            "output": output,
            "scope": wizard._scope(),
            "result": result,
            "profile_id": wizard.profile_id.id if wizard.profile_id else False,
            "line_count": counters.get("lines", 0),
            "payslip_count": counters.get("payslips", 0),
            "warning_count": counters.get("warnings", 0),
            "detail": (detail or "")[:80],
        })
