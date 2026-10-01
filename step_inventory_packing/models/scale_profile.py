"""Perfiles de lectura para balanzas BLE GATT y serie Bluetooth/USB."""

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StepScaleProfile(models.Model):
    _name = "step.scale.profile"
    _description = "Perfil de balanza"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    protocol = fields.Selection([
        ("ble", "Bluetooth BLE (GATT)"),
        ("serial", "Puerto serie (Bluetooth SPP / USB)"),
    ], required=True, default="serial")
    service_uuid = fields.Char(string="UUID servicio BLE")
    characteristic_uuid = fields.Char(string="UUID característica BLE")
    serial_service_uuid = fields.Char(string="UUID servicio serie RFCOMM personalizado")
    baud_rate = fields.Integer(string="Baudios", default=9600)
    weight_pattern = fields.Char(
        string="Expresión de peso", required=True,
        default=r"([-+]?\d+(?:[.,]\d+)?)\s*(?:kg)?\r?\n",
        help="El primer grupo captura el peso. Ajuste el patrón al formato completo de la trama y al indicador de estabilidad del equipo.")
    kg_factor = fields.Float(string="Multiplicador a kg", default=1.0, required=True)
    notes = fields.Text(string="Modelo y formato de trama")

    @api.constrains("protocol", "service_uuid", "characteristic_uuid", "baud_rate", "weight_pattern", "kg_factor")
    def _check_profile(self):
        for profile in self:
            if profile.protocol == "ble" and (not profile.service_uuid or not profile.characteristic_uuid):
                raise ValidationError(_("Indique UUID de servicio y característica para BLE."))
            if profile.protocol == "serial" and not 300 <= profile.baud_rate <= 921600:
                raise ValidationError(_("La velocidad del puerto serie no es válida."))
            if profile.kg_factor <= 0:
                raise ValidationError(_("El multiplicador a kg debe ser positivo."))
            try:
                pattern = re.compile(profile.weight_pattern or "")
            except re.error as exc:
                raise ValidationError(_("Expresión de peso inválida: %s") % exc) from exc
            if pattern.groups < 1:
                raise ValidationError(_("La expresión de peso debe tener un grupo de captura."))
