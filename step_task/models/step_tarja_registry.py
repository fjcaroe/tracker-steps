# -*- coding: utf-8 -*-

from odoo import fields, models


class StepTarjaRegistry(models.Model):
    """Línea de detalle de la OT con metadatos de captura móvil."""

    _inherit = 'step.tarja.registry'

    mobile_uid = fields.Char(
        string='UID móvil',
        copy=False,
        index=True,
        help="Identificador único de la línea generado por la app. Evita "
             "duplicados al reintentar la sincronización.",
    )
    read_method = fields.Selection(
        selection=[
            ('manual', 'Manual'),
            ('barcode', 'Código de barra'),
            ('qr', 'QR'),
            ('nfc', 'NFC'),
        ],
        string='Método de lectura',
        default='manual',
        copy=False,
    )
    event_datetime = fields.Datetime(
        string='Fecha/hora de registro',
        copy=False,
        help="Momento en que la app registró la cantidad del trabajador.",
    )
    relacion_trato = fields.Many2one(
        'uom.uom',
        string='Relación Trato',
        help="Unidad de la relación de trato de la labor (copiada del producto).",
    )
