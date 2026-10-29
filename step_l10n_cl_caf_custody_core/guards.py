"""Prevent token/public exposure and revalidate cached binary downloads."""
from odoo import _, api, models
from odoo.exceptions import AccessError

from .custody import MODEL, company_rut, decode_original, parse_original


class Attachment(models.Model):
    _inherit = 'ir.attachment'

    def _step_caf_attachments(self):
        return self.filtered(lambda row: row.res_model == MODEL)

    def _step_check_private_caf(self):
        if any(row.public or row.access_token or row.type != 'binary' for row in self._step_caf_attachments()):
            raise AccessError(_('Los archivos CAF permanecen privados y no admiten enlaces con token.'))

    def _step_claim_caf_targets(self, vals_list):
        owners = set()
        for values in vals_list:
            model = values.get('res_model', self.env.context.get('default_res_model'))
            if model != MODEL:
                continue
            record_id = values.get('res_id', self.env.context.get('default_res_id'))
            field = values.get('res_field', self.env.context.get('default_res_field'))
            if type(record_id) is not int or not record_id or field != 'caf_file':
                raise AccessError(_('La custodia requiere el registro y campo CAF originales.'))
            owners.add(record_id)
        if not owners:
            return owners
        records = self.env[MODEL].browse(sorted(owners)).exists()
        if set(records.ids) != owners:
            raise AccessError(_('El archivo CAF requiere su registro original persistido.'))
        records._step_custody_scope('write')
        # Odoo uses REPEATABLE READ. A row lock alone does not invalidate another
        # writer's earlier snapshot. Touch the same PK value, before inserting
        # payload, so concurrent attachment writers serialize or retry. No value,
        # write_date, master ID, fiscal counter or historical amount changes.
        self.env.cr.execute('UPDATE l10n_cl_dte_caf SET id=id WHERE id=ANY(%s) RETURNING id', [sorted(owners)])
        if {row[0] for row in self.env.cr.fetchall()} != owners:
            raise AccessError(_('El registro CAF original ya no está disponible.'))
        self.env.cr.execute('SELECT res_id FROM ir_attachment WHERE res_model=%s AND res_field=%s '
                            'AND res_id=ANY(%s) LIMIT 1', [MODEL, 'caf_file', sorted(owners)])
        if self.env.cr.fetchone():
            raise AccessError(_('El CAF ya tiene un archivo original; la custodia no crea copias ambiguas.'))
        return owners

    def _step_check_caf_owners(self):
        attachments = self._step_caf_attachments()
        if any(row.res_field != 'caf_file' for row in attachments):
            raise AccessError(_('La custodia usa el campo y adjunto CAF originales.'))
        owners = sorted(set(attachments.mapped('res_id')))
        if not owners:
            return
        records = self.env[MODEL].browse(owners).exists()
        if sorted(records.ids) != owners:
            raise AccessError(_('El archivo CAF requiere su registro original persistido.'))
        records._step_custody_scope('write')
        self.env.cr.execute('SELECT res_id FROM ir_attachment WHERE res_model=%s AND res_field=%s '
                            'AND res_id=ANY(%s) GROUP BY res_id HAVING count(*)>1', [MODEL, 'caf_file', owners])
        if self.env.cr.fetchone():
            raise AccessError(_('El CAF ya tiene un archivo original; la custodia no crea copias ambiguas.'))
        by_id = {record.id: record for record in records}
        for attachment in attachments:
            parsed = parse_original(decode_original(attachment.with_context(bin_size=False).datas))
            if parsed.issuer_rut != company_rut(by_id[attachment.res_id].company_id):
                raise AccessError(_('El emisor del archivo debe coincidir con la empresa del CAF.'))

    @api.model_create_multi
    def create(self, vals_list):
        with self.env.cr.savepoint():
            claimed = self._step_claim_caf_targets(vals_list)
            records = super().create(vals_list)
            records._step_check_private_caf()
            if set(records._step_caf_attachments().mapped('res_id')) != claimed:
                raise AccessError(_('La carga CAF requiere una identidad de adjunto explícita.'))
            records._step_check_caf_owners()
            return records

    def write(self, vals):
        if vals.get('res_model') == MODEL:
            raise AccessError(_('La custodia no reasigna archivos existentes a otro CAF.'))
        if self._step_caf_attachments() and set(vals) & {'datas', 'raw', 'db_datas', 'store_fname', 'res_model', 'res_id', 'res_field'}:
            raise AccessError(_('El archivo original del CAF en custodia no se reemplaza ni se reasigna.'))
        with self.env.cr.savepoint():
            result = super().write(vals)
            self._step_check_private_caf()
            return result

    def unlink(self):
        if self._step_caf_attachments():
            raise AccessError(_('El archivo original del CAF en custodia no se elimina.'))
        return super().unlink()


class Binary(models.AbstractModel):
    _inherit = 'ir.binary'

    def _step_check_caf_stream(self, record):
        if record._name == MODEL:
            self.env[MODEL].browse(record.ids)._step_custody_scope()
        elif record._name == 'ir.attachment' and record.res_model == MODEL:
            # super may have returned sudo() after validating a token. Rebind
            # the CAF to the actual caller before any bytes reach the stream.
            record._step_check_private_caf()
            self.env[MODEL].browse(record.res_id)._step_custody_scope()

    def _find_record(self, xmlid=None, res_model='ir.attachment', res_id=None,
                     access_token=None, field=None):
        record = super()._find_record(xmlid=xmlid, res_model=res_model, res_id=res_id,
                                       access_token=access_token, field=field)
        self._step_check_caf_stream(record)
        return record

    def _record_to_stream(self, record, field_name):
        self._step_check_caf_stream(record)
        return super()._record_to_stream(record, field_name)
