"""Private download of approved existing payments; no batch model is simulated."""
import base64

from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, UserError


class BankExportWizard(models.TransientModel):
    _name = 'step.bank.export.wizard'
    _description = 'Archivo bancario de pagos existentes'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.ref('base.CLP'), readonly=True)
    bank_format = fields.Selection([('bancoestado', 'BancoEstado: Pago 7 Columnas (.xlsx)'),
                                    ('security', 'Security: nómina sin detalles (.xls)')],
                                   required=True, default='bancoestado', string='Formato')
    payment_ids = fields.Many2many('account.payment', 'step_bank_export_wizard_payment_rel',
                                  'wizard_id', 'payment_id', check_company=True, string='Pagos existentes')
    amount_total = fields.Monetary(compute='_compute_amount_total', string='Total CLP')
    security_description = fields.Char(string='Glosa Security')
    file_data = fields.Binary(string='Archivo privado', attachment=False, readonly=True)
    file_name = fields.Char(string='Nombre de archivo', readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        for field in ('file_data', 'file_name'):
            if field in fields_list:
                values[field] = False
        if 'payment_ids' in fields_list and self.env.context.get('active_model') == 'account.payment':
            values['payment_ids'] = [Command.set(self.env.context.get('active_ids', []))]
        return values

    @api.depends('payment_ids.amount')
    def _compute_amount_total(self):
        for wizard in self:
            wizard.amount_total = sum(wizard.payment_ids.mapped('amount'))

    @api.constrains('company_id', 'payment_ids')
    def _check_scope(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise AccessError(_('Generar archivos bancarios requiere el perfil de responsable de Contabilidad.'))
        for wizard in self:
            if wizard.company_id not in self.env.companies:
                raise UserError(_('Seleccione una empresa activa.'))
            if wizard.payment_ids:
                self.env['step.bank.export.service']._payments(wizard.payment_ids, wizard.company_id)

    @api.constrains('currency_id')
    def _check_currency(self):
        if any(wizard.currency_id != self.env.ref('base.CLP') for wizard in self):
            raise UserError(_('Los archivos bancarios chilenos se expresan en CLP.'))

    @api.model_create_multi
    def create(self, values_list):
        if any({'create_uid', 'create_date', 'write_uid', 'write_date', 'id'} & values.keys()
               for values in values_list):
            raise AccessError(_('La propiedad del asistente la determina el usuario que lo crea.'))
        if any({'file_data', 'file_name'} & values.keys() for values in values_list):
            raise UserError(_('El archivo debe generarse desde los pagos seleccionados.'))
        return super().create(values_list)

    def write(self, values):
        if {'create_uid', 'create_date', 'write_uid', 'write_date', 'id'} & values.keys():
            raise AccessError(_('La propiedad del asistente la determina el usuario que lo crea.'))
        if {'file_data', 'file_name'} & values.keys():
            raise UserError(_('El archivo debe generarse desde los pagos seleccionados.'))
        if {'company_id', 'payment_ids', 'bank_format', 'security_description'} & values.keys():
            values = dict(values, file_data=False, file_name=False)
        return super().write(values)

    def _check_legacy_approval(self):
        """Honor a native Treasury policy while its batch adapter still exists.

        This wizard cannot replace or manufacture a batch approval. Above an
        existing company threshold only its configured approver may download.
        """
        self.ensure_one()
        company = self.company_id
        if 'treasury_batch_approval_threshold' not in company._fields:
            return
        threshold = company.treasury_batch_approval_threshold
        if threshold and self.amount_total > threshold and (
                not company.treasury_batch_approver_id or self.env.user != company.treasury_batch_approver_id):
            raise UserError(_('El total supera el tope de Tesorería; debe exportarlo el aprobador configurado.'))

    def action_generate_file(self):
        self.ensure_one()
        self.check_access('write')
        self._check_scope()
        self._check_legacy_approval()
        service = self.env['step.bank.export.service']
        if self.bank_format == 'bancoestado':
            payload = service.bancoestado_file(self.payment_ids, self.company_id)
            prefix, extension = 'BANCOESTADO_7_COLUMNAS', 'xlsx'
        else:
            payload = service.security_file(self.payment_ids, self.company_id, self.security_description)
            prefix, extension = 'SECURITY', 'xls'
        filename = '%s_%s_%s.%s' % (prefix, fields.Date.context_today(self).strftime('%Y%m%d'), self.id, extension)
        # A direct call to the parent is confined to bytes produced above. The
        # public create/write API cannot accept an arbitrary bank file.
        super().write({'file_data': base64.b64encode(payload), 'file_name': filename})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}

    def action_download(self):
        self.ensure_one()
        self.check_access('read')
        self._check_scope()
        self._check_legacy_approval()
        if not self.file_data:
            raise UserError(_('Genere primero el archivo de los pagos seleccionados.'))
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content?model=%s&id=%s&field=file_data&filename_field=file_name&download=true' % (
                    self._name, self.id)}
