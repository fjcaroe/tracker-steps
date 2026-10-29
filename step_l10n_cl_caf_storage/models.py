import base64

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.addons.step_l10n_cl_caf_custody_core.custody import (
    CAFCustodyMixin, MODEL, company_rut, decode_original, parse_original,
)
from .hooks import check_model_registration


class CAFCustody(CAFCustodyMixin, models.Model):
    _name = MODEL
    _table = 'l10n_cl_dte_caf'
    _description = 'Custodia privada CAF'
    _rec_name = 'filename'

    # Same eight declared fields plus six automatic fields: fourteen in total.
    # No authentication flag, duplicate master, folio counter or extra column.
    filename = fields.Char(string='Archivo')
    caf_file = fields.Binary(string='CAF original', attachment=True)
    issued_date = fields.Date(string='Fecha de autorización')
    l10n_latam_document_type_id = fields.Many2one('l10n_latam.document.type', string='Tipo de documento')
    start_nb = fields.Integer(string='Folio inicial')
    final_nb = fields.Integer(string='Folio final')
    company_id = fields.Many2one('res.company', string='Empresa', readonly=True,
                                  default=lambda self: self.env.company)
    status = fields.Selection([('in_use', 'En uso'), ('spent', 'Agotado')], string='Estado legado')

    _sql_constraints = [('filename_unique', 'unique(filename)', 'El nombre del archivo CAF debe ser único.')]

    @classmethod
    def _build_model(cls, pool, cr):
        check_model_registration(pool, cr)
        return super()._build_model(pool, cr)

    @api.model
    def _step_prepare_custody_values(self, values):
        if not (self.env.user.has_group('account.group_account_manager')
                or self.env.user.has_group('stock.group_stock_manager')):
            raise AccessError(_('La carga CAF requiere el perfil responsable de Contabilidad o Inventario.'))
        self.check_access('create')
        values = dict(values)
        if set(values) & {'id', 'create_uid', 'write_uid', 'create_date', 'write_date', 'display_name'}:
            raise UserError(_('La carga no permite reemplazar la identidad ni la auditoría original.'))
        raw = decode_original(values.get('caf_file'))
        parsed = parse_original(raw)
        company = self.env['res.company'].browse(values.get('company_id') or self.env.company.id)
        company.ensure_one()
        company.check_access('read')
        if company != self.env.company or company not in self.env.companies or parsed.issuer_rut != company_rut(company):
            raise UserError(_('El emisor del CAF debe coincidir con la empresa activa seleccionada.'))
        document = self.env['l10n_latam.document.type'].browse(values.get('l10n_latam_document_type_id'))
        if not document:
            document = self.env['l10n_latam.document.type'].search([
                ('country_id.code', '=', 'CL'), ('code', '=', str(parsed.document_type))])
        document.check_access('read')
        if len(document) != 1 or document.country_id.code != 'CL' or document.code != str(parsed.document_type):
            raise UserError(_('Seleccione el único tipo de documento chileno correspondiente al CAF.'))
        expected = {'company_id': company.id, 'l10n_latam_document_type_id': document.id,
                    'start_nb': parsed.folio_from, 'final_nb': parsed.folio_to,
                    'issued_date': parsed.authorization_date}
        for name, value in expected.items():
            supplied = values.get(name)
            if name == 'issued_date' and supplied:
                supplied = fields.Date.to_date(supplied)
            if name in values and supplied not in (False, None) and supplied != value:
                raise UserError(_('Los datos indicados no coinciden con el archivo CAF original.'))
        if values.get('status'):
            raise UserError(_('Una carga de custodia no habilita ni agota folios.'))
        filename = values.get('filename')
        if not isinstance(filename, str) or not filename.strip() or any(char in filename for char in ('\r', '\n', '\x00')):
            raise UserError(_('Indique el nombre del archivo CAF.'))
        if self.search_count([('filename', '=', filename)]):
            raise UserError(_('Ya existe un archivo CAF con ese nombre.'))
        values.update(expected, caf_file=base64.b64encode(raw), status=False)
        return values

    @api.model_create_multi
    def create(self, vals_list):
        prepared = [self._step_prepare_custody_values(values) for values in vals_list]
        with self.env.cr.savepoint():
            return super().create(prepared)

    @api.model
    def step_custody_upload(self, filename, file_data, company_id=None, document_type_id=None):
        values = {'filename': filename, 'caf_file': file_data, 'company_id': company_id or self.env.company.id}
        if document_type_id:
            values['l10n_latam_document_type_id'] = document_type_id
        record = self.create(values)
        return {'type': 'ir.actions.act_window', 'res_model': MODEL,
                'res_id': record.id, 'view_mode': 'form', 'target': 'current'}

    def write(self, vals):
        self._step_custody_scope('write')
        if vals:
            raise UserError(_('La custodia conserva el CAF y sus datos originales; no reemplaza archivos ni estados históricos.'))
        return super().write(vals)

    def unlink(self):
        self._step_custody_scope('unlink')
        raise UserError(_('Los registros y archivos CAF en custodia se conservan.'))

    def action_enable(self):
        return self.step_custody_reserve_folio()

    def action_spend(self):
        return self.step_custody_reserve_folio()


class DocumentType(models.Model):
    _inherit = 'l10n_latam.document.type'

    l10n_cl_dte_caf_ids = fields.One2many(MODEL, 'l10n_latam_document_type_id', string='CAF')
