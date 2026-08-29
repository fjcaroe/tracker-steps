# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessDenied

TOKEN_TTL_MINUTES = 60 * 8  # jornada laboral típica; corto a propósito
PAIRING_CODE_TTL_MINUTES = 15


class StepMobilizationDriverDevice(models.Model):
    """Asociación chofer <-> dispositivo móvil.

    El chofer se modela como res.partner (no siempre es hr.employee), y el
    encargo prohíbe usar el PIN de trabajador como credencial. En vez de
    inventar un PIN nuevo sobre res.partner, la asociación se hace con un
    código de emparejamiento de un solo uso emitido por un operador desde el
    backend (patrón estándar de "device pairing"): no se guarda PIN ni token
    en texto plano, sólo hashes."""
    _name = 'step.mobilization.driver.device'
    _description = 'Dispositivo móvil de chofer'
    _rec_name = 'device_label'

    chofer_id = fields.Many2one('res.partner', string='Chofer', required=True,
                                 domain=[('step_chofer', '=', True)])
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                  default=lambda self: self.env.company)
    device_uuid = fields.Char(string='UUID del dispositivo', copy=False, index=True,
                               help='Se completa solo cuando el chofer reclama el código de emparejamiento.')
    device_label = fields.Char(string='Etiqueta', compute='_compute_device_label', store=True)
    state = fields.Selection(
        selection=[('pending', 'Pendiente de emparejar'), ('active', 'Activo'), ('revoked', 'Revocado')],
        string='Estado', default='pending', required=True)
    pairing_code_hash = fields.Char(string='Hash de código de emparejamiento', copy=False)
    pairing_code_expires_at = fields.Datetime(string='Código expira', copy=False)
    token_hash = fields.Char(string='Hash de token', copy=False)
    token_expires_at = fields.Datetime(string='Token expira', copy=False)
    last_seen = fields.Datetime(string='Última actividad', copy=False)

    _sql_constraints = [
        ('device_uuid_company_unique', 'unique(device_uuid, company_id)',
         'Este dispositivo ya está registrado en esta compañía.'),
    ]

    @api.depends('chofer_id', 'device_uuid', 'state')
    def _compute_device_label(self):
        for record in self:
            suffix = (record.device_uuid or record.state)[:8]
            record.device_label = '%s — %s' % (record.chofer_id.name or '?', suffix)

    def action_generate_pairing_code(self):
        """Genera (o regenera) un código de 8 dígitos, válido 15 minutos, que
        el operador entrega al chofer fuera de banda (verbalmente/impreso) —
        nunca por este mismo canal."""
        self.ensure_one()
        code = '%08d' % secrets.randbelow(10 ** 8)
        self.write({
            'pairing_code_hash': self._hash(code),
            'pairing_code_expires_at': fields.Datetime.now() + timedelta(minutes=PAIRING_CODE_TTL_MINUTES),
            'device_uuid': False,
            'state': 'pending',
        })
        return code

    def action_revoke(self):
        self.write({'state': 'revoked', 'token_hash': False, 'token_expires_at': False, 'device_uuid': False})

    @staticmethod
    def _hash(value):
        return hashlib.sha256(value.encode()).hexdigest()

    @api.model
    def _claim(self, chofer_pairing_code, device_uuid):
        """Primer contacto de la app: intercambia el código de emparejamiento
        por un token. Idempotente por device_uuid: si el mismo dispositivo ya
        reclamó un código válido, no se puede reclamar dos veces (el segundo
        intento debe pasar por login normal)."""
        code_hash = self._hash(chofer_pairing_code)
        device = self.sudo().search([
            ('pairing_code_hash', '=', code_hash), ('state', '=', 'pending')], limit=1)
        if not device or not device.pairing_code_expires_at or device.pairing_code_expires_at < fields.Datetime.now():
            raise AccessDenied('Código de emparejamiento inválido o expirado.')
        device.write({
            'device_uuid': device_uuid,
            'state': 'active',
            'pairing_code_hash': False,
            'pairing_code_expires_at': False,
        })
        return device, device._issue_token()

    def _issue_token(self):
        self.ensure_one()
        if self.state != 'active':
            raise AccessDenied('Dispositivo no activo.')
        raw_token = secrets.token_urlsafe(32)
        self.write({
            'token_hash': self._hash(raw_token),
            'token_expires_at': fields.Datetime.now() + timedelta(minutes=TOKEN_TTL_MINUTES),
            'last_seen': fields.Datetime.now(),
        })
        return raw_token

    @api.model
    def _authenticate(self, device_uuid, token):
        device = self.sudo().search([('device_uuid', '=', device_uuid), ('state', '=', 'active')], limit=1)
        if not device or not device.token_hash or not device.token_expires_at:
            raise AccessDenied('Dispositivo o token inválido.')
        if device.token_expires_at < fields.Datetime.now():
            raise AccessDenied('Token expirado.')
        if not secrets.compare_digest(device.token_hash, device._hash(token)):
            raise AccessDenied('Token inválido.')
        device.sudo().write({'last_seen': fields.Datetime.now()})
        return device

    @api.model
    def _refresh(self, device_uuid, token):
        device = self._authenticate(device_uuid, token)
        return device, device.sudo()._issue_token()
