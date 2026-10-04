from odoo import fields, models


class StepDispatchTransferReason(models.Model):
    """Razón del traslado (tabla SII "Indicador tipo de traslado de bienes").

    El código es el que se informa en el Libro de Guías de Despacho: 1 es
    venta y se puede facturar; 2 a 9 son traslados que no constituyen venta.
    """

    _name = "step.dispatch.transfer.reason"
    _description = "Razón del traslado"
    _order = "sequence, code"

    code = fields.Char(string="Código SII", required=True)
    name = fields.Char(string="Razón del traslado", required=True, translate=True)
    invoiceable = fields.Boolean(
        string="Facturable",
        help="Las guías con esta razón aparecen en Facturar guías.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Ya existe una razón de traslado con ese código."),
    ]

    def _compute_display_name(self):
        for reason in self:
            reason.display_name = f"{reason.code}. {reason.name}" if reason.code else reason.name


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Mismo campo que define step_mobilization (pestaña Movilización). Se
    # declara aquí también para que las guías funcionen en bases sin ese
    # módulo; ambos módulos comparten la misma columna.
    step_chofer = fields.Boolean(string="¿Chofer?")
