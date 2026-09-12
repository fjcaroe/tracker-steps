from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    step_hrs_machinery_line_id = fields.Many2one(
        "step.hrs.machinery.line", string="Línea de horas máquina",
        readonly=True, copy=False, ondelete="restrict", index=True,
        help="Línea de consumo de combustible de Horas Máquina que generó "
             "este movimiento. Permite trazar el centro de costos, la "
             "temporada y la actividad hasta el registro de Inventario.",
    )
