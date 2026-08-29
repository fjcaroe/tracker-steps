# -*- coding: utf-8 -*-

import uuid

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_movi = fields.Boolean('Usa servicio movilización')
    recorrido_id = fields.Many2one('hr.route', 'Recorrido habitual')
    mobile_credential_uuid = fields.Char(
        string='Credencial móvil (QR/NFC)', copy=False, readonly=True, index=True,
        default=lambda self: str(uuid.uuid4()),
        help='Identificador opaco impreso/codificado en la credencial física. '
             'No es el PIN y no debe usarse como clave: sólo sirve para que la app '
             'móvil resuelva de qué trabajador se trata antes de pedir el PIN.')

    _sql_constraints = [
        ('mobile_credential_uuid_unique', 'unique(mobile_credential_uuid)',
         'La credencial móvil debe ser única.'),
    ]
