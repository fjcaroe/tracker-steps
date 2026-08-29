"""Configuración previsional de las jornadas de trabajo."""

from odoo import fields, models


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    previred_workday_type = fields.Selection(
        selection=[
            ("1", "Jornada completa"),
            ("2", "Jornada parcial"),
        ],
        string="Código jornada Previred",
        default="1",
        required=True,
        help=(
            "Código que se informa en el campo 93 del archivo Previred. "
            "Use 1 para jornada completa y 2 para jornada parcial."
        ),
    )
