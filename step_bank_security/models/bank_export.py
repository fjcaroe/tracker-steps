"""T104: Excel 97–2003 sin detalles, conforme al adjunto del banco."""
import base64
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
# Keep these public helper imports available to existing callers and tests.
from odoo.addons.step_bank_export_core.models.bank_export_service import clean_rut, whole_pesos, BANK_CODES


class BatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    security_description = fields.Char(string='Glosa Security', copy=False,
                                      help='Opcional, hasta 100 caracteres. Si está vacía se usa la referencia de cada pago.')
    security_export_count = fields.Integer(string='Exportaciones Security', default=0, readonly=True, copy=False)

    @api.constrains('security_description')
    def _check_security_description(self):
        if any(len(batch.security_description or '') > 100 for batch in self):
            raise ValidationError(_('La glosa Security admite hasta 100 caracteres.'))

    def _security_rows(self):
        self.ensure_one()
        self.check_access('write')
        if self.batch_type != 'outbound' or not self.payment_ids:
            raise UserError(_('Seleccione un lote saliente con pagos.'))
        if self.company_id not in self.env.companies:
            raise UserError(_('El lote no pertenece a una empresa activa.'))
        self._check_batch_approval()
        return self.env['step.bank.export.service'].security_rows(
            self._treasury_export_payments(), self.company_id, self.security_description)

    def action_export_security_xls(self):
        rows = self._security_rows()
        payload = self.env['step.bank.export.service'].security_file(
            self._treasury_export_payments(), self.company_id, self.security_description)
        safe = re.sub(r'[^A-Za-z0-9_-]', '_', self.name or 'lote')
        attachment = self.env['ir.attachment'].create({
            'name': safe + '_SECURITY.xls', 'type': 'binary', 'mimetype': 'application/vnd.ms-excel',
            'datas': base64.b64encode(payload), 'res_model': self._name, 'res_id': self.id})
        self.security_export_count += 1
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id, 'target': 'self'}
