# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    step_phyto_policy = fields.Selection(
        selection=[
            ("off", "Desactivado"),
            ("warn", "Advertir al aprobar"),
            ("block", "Bloquear la aprobación"),
        ],
        string="Control de carencia en cosecha",
        default="warn",
        required=True,
        help=(
            "Qué hacer cuando se aprueba un registro de cosecha de un cuartel "
            "que todavía está en período de carencia.\n"
            "· Desactivado: no se verifica.\n"
            "· Advertir: se registra la alerta en el historial del registro.\n"
            "· Bloquear: se impide aprobar hasta que venza la carencia."
        ),
    )
    step_phyto_criterion = fields.Selection(
        selection=[
            ("label", "Etiqueta (SAG)"),
            ("max", "La mayor de todas"),
            ("eu", "Unión Europea"),
            ("usa", "Estados Unidos"),
        ],
        string="Criterio de carencia",
        default="max",
        required=True,
        help=(
            "Qué valor de días de carencia se usa para calcular la fecha "
            "mínima de cosecha. La etiqueta es la exigencia legal en Chile; "
            "los mercados de destino suelen ser más restrictivos, por lo que "
            "el valor por defecto es el más conservador."
        ),
    )
