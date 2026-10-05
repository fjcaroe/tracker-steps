"""Vendor-configurable transports; label language is explicitly selected (ZPL)."""
import unicodedata

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


def label_text(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode()
    return ''.join(char for char in text if 32 <= ord(char) < 127 and char not in '^~\\').strip()[:90]


class PrinterProfile(models.Model):
    _name = 'step.printer.profile'
    _description = 'Perfil de impresora de tarjas'
    _order = 'name'
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    protocol = fields.Selection([('pdf', 'PDF / controlador del sistema'), ('serial', 'USB serie / Bluetooth SPP'),
        ('usb', 'USB directo (WebUSB)'), ('ble', 'Bluetooth BLE (GATT)')], required=True, default='pdf')
    language = fields.Selection([('zpl', 'ZPL')], default='zpl', required=True)
    baud_rate = fields.Integer(default=9600)
    serial_service_uuid = fields.Char('UUID servicio RFCOMM personalizado')
    service_uuid = fields.Char('UUID servicio BLE')
    characteristic_uuid = fields.Char('UUID característica BLE de escritura')
    usb_vendor_id = fields.Integer('USB Vendor ID (decimal)')
    usb_product_id = fields.Integer('USB Product ID (decimal)')
    usb_configuration = fields.Integer('Configuración USB', default=1)
    usb_interface = fields.Integer('Interfaz USB', default=0)
    usb_endpoint = fields.Integer('Endpoint OUT USB', default=1)
    chunk_size = fields.Integer('Bytes por bloque BLE', default=20)
    label_width = fields.Integer('Ancho etiqueta (dots)', default=800)
    label_height = fields.Integer('Alto etiqueta (dots)', default=600)
    notes = fields.Text('Modelo, controlador y homologación')

    @api.constrains('protocol', 'baud_rate', 'service_uuid', 'characteristic_uuid', 'usb_vendor_id',
                    'usb_product_id', 'usb_configuration', 'usb_interface', 'usb_endpoint', 'chunk_size', 'label_width', 'label_height')
    def _check_profile(self):
        for row in self:
            if not 300 <= row.baud_rate <= 921600 or not 1 <= row.chunk_size <= 512:
                raise ValidationError(_('Revise la velocidad serie y el tamaño de bloque BLE.'))
            if not 400 <= row.label_width <= 2400 or not 400 <= row.label_height <= 2400:
                raise ValidationError(_('El tamaño de etiqueta debe estar entre 400 y 2400 dots.'))
            if row.protocol == 'ble' and (not row.service_uuid or not row.characteristic_uuid):
                raise ValidationError(_('Indique los UUID del fabricante para la escritura BLE.'))
            if row.protocol == 'usb' and (not 1 <= row.usb_vendor_id <= 65535 or not 0 <= row.usb_product_id <= 65535 or
                    not 1 <= row.usb_configuration <= 255 or not 0 <= row.usb_interface <= 255 or not 1 <= row.usb_endpoint <= 15):
                raise ValidationError(_('Configure Vendor ID, interfaz y endpoint OUT según el equipo USB.'))

    def _client_job(self, payload):
        self.ensure_one()
        self.check_access('read')
        if self.company_id not in self.env.companies or not self.active:
            raise UserError(_('Seleccione una impresora activa de una empresa habilitada.'))
        return {'type': 'ir.actions.client', 'tag': 'step_printer_job', 'name': _('Imprimir tarja'),
            'params': {'payload': payload, 'profile': {name: self[name] for name in (
                'name', 'protocol', 'baud_rate', 'serial_service_uuid', 'service_uuid', 'characteristic_uuid',
                'usb_vendor_id', 'usb_product_id', 'usb_configuration', 'usb_interface', 'usb_endpoint', 'chunk_size')}}}

    def action_test_label(self):
        self.ensure_one()
        if self.protocol == 'pdf':
            raise UserError(_('El perfil PDF usa el informe de tarja y el controlador de impresión del sistema.'))
        return self._client_job('^XA^PW%s^LL%s^FO30,40^A0N,30,30^FDPRUEBA PACKING / %s^FS^XZ' % (
            self.label_width, self.label_height, label_text(self.name)))


class PrintWizard(models.TransientModel):
    _name = 'step.printer.job.wizard'
    _description = 'Seleccionar impresora de tarja'
    package_id = fields.Many2one('stock.quant.package', string='Tarja', required=True)
    profile_id = fields.Many2one('step.printer.profile', string='Impresora', required=True)

    def action_prepare(self):
        self.ensure_one()
        tag = self.package_id
        tag.check_access('read')
        profile = self.profile_id
        profile.check_access('read')
        if tag.company_id and tag.company_id != profile.company_id or profile.company_id not in self.env.companies:
            raise UserError(_('La impresora debe corresponder a la empresa de la tarja.'))
        if not tag.is_fruit_tag:
            raise UserError(_('Seleccione una tarja de fruta.'))
        if profile.protocol == 'pdf':
            return self.env.ref('step_inventory_fruit_tag.action_report_fruit_tag').report_action(tag)
        return profile._client_job(tag._zpl_label(profile))


class FruitPackage(models.Model):
    _inherit = 'stock.quant.package'

    def _zpl_label(self, profile):
        self.ensure_one()
        code = label_text(self.name)
        if not code or code != self.name:
            raise UserError(_('El código de tarja debe ser ASCII imprimible sin comandos ZPL para conservar su lectura exacta.'))
        return '^XA^PW%s^LL%s^FO30,30^A0N,35,35^FD%s^FS^FO30,85^A0N,25,25^FD%s / %s^FS^FO30,125^A0N,25,25^FD%s / %.3f KG^FS^FO30,175^BQN,2,6^FDLA,%s^FS^XZ' % (
            profile.label_width, profile.label_height, code, label_text(self.especie_id.display_name),
            label_text(self.variedad_id.display_name), label_text(self.step_producer_id.display_name), self.step_actual_kg, code)

    def action_choose_label_printer(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': _('Impresora de tarja'), 'res_model': 'step.printer.job.wizard',
            'view_mode': 'form', 'target': 'new', 'context': {'default_package_id': self.id}}
