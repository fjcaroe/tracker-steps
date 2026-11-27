from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import SQL
from odoo.tools.misc import unquote
from odoo.models import to_company_ids


class SharedMaster(models.AbstractModel):
    _name = 'step.shared.agriculture.master'
    _description = 'Asignación explícita de maestros a empresas y sucursales'

    def _check_company_domain(self, companies):
        # Native relational consistency and generated selector domains use this
        # hook. Keep the historical owner instead of clearing company_id.
        if isinstance(companies, unquote):
            return [('company_ids', 'in', companies)]
        return [('company_ids', 'in', to_company_ids(companies))] if companies else [('id', '=', False)]

    @api.model_create_multi
    def create(self, vals_list):
        values = []
        for supplied in vals_list:
            vals = dict(supplied)
            vals.setdefault('company_id', self.env.company.id)
            vals.setdefault('company_ids', [(6, 0, [vals['company_id']])])
            values.append(vals)
        records = super().create(values)
        if not self.env.su and any(set(r.company_ids.ids) - set(self.env.user.company_ids.ids) for r in records):
            raise AccessError(_('No puede asignar empresas sin acceso.'))
        records._check_memberships()
        return records

    def write(self, vals):
        if 'company_id' in vals and any(r.company_id.id != vals['company_id'] for r in self):
            raise ValidationError(_('La empresa de origen se conserva. Cambie las empresas y sucursales permitidas.'))
        old = {r.id: set(r.company_ids.ids) for r in self}
        result = super().write(vals)
        if 'company_ids' in vals:
            for record in self:
                changed = old[record.id] ^ set(record.company_ids.ids)
                if not self.env.su and changed - set(self.env.user.company_ids.ids):
                    raise AccessError(_('Solo puede cambiar la asignación de las empresas a las que tiene acceso.'))
            self._check_memberships()
            self._check_document_memberships(old)
        if 'code' in vals:
            self._check_memberships()
        return result

    @api.constrains('company_ids', 'company_id')
    def _check_memberships(self):
        for record in self:
            if not record.company_ids or record.company_id not in record.company_ids:
                raise ValidationError(_('Seleccione al menos la empresa de origen; puede agregar otras empresas y sucursales.'))
            if 'code' in record and record.code:
                # Prevent overlapping codes also between records with different
                # historical owners; serialize competing assignments by code.
                self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', [self._name + ':' + record.code])
                duplicate = self.sudo().with_context(active_test=False).search_count([
                    ('id', '!=', record.id), ('code', '=', record.code),
                    ('company_ids', 'in', record.company_ids.ids)])
                if duplicate:
                    raise ValidationError(_('El código ya existe en alguna de las empresas seleccionadas.'))

    def _check_document_memberships(self, old):
        # Refuse removal of a company used by an existing document. Preserve
        # IDs and historical selections; never silently reassign documents.
        for model_name in self.env.registry:
            model = self.env[model_name]
            if not model._auto or model._abstract or model._transient or 'company_id' not in model._fields:
                continue
            company_field = model._fields['company_id']
            if not company_field.store or company_field.type != 'many2one':
                continue
            for name, field in model._fields.items():
                if field.type != 'many2one' or field.comodel_name != self._name or not field.store:
                    continue
                for record in self:
                    removed = old[record.id] - set(record.company_ids.ids)
                    if not removed:
                        continue
                    self.env.cr.execute(SQL('SELECT 1 FROM %s WHERE %s = %s AND company_id IN %s LIMIT 1',
                        SQL.identifier(model._table), SQL.identifier(name), record.id, tuple(removed)))
                    if self.env.cr.fetchone():
                        raise ValidationError(_('Una empresa utiliza este maestro en documentos existentes. Conserve su asignación.'))


class Fundo(models.Model):
    _name = 'step.fundo'
    _inherit = ['step.fundo', 'step.shared.agriculture.master']
    company_ids = fields.Many2many('res.company', 'step_fundo_company_rel', 'master_id', 'company_id', string='Empresas y sucursales', required=True, default=lambda self: self.env.company)

    def _check_document_memberships(self, old):
        super()._check_document_memberships(old)
        # A restored installation can contain document tables whose application
        # is still being migrated. A real FK still protects a farm assignment
        # in those documents even when its model is absent from this registry.
        removed = [(record.id, tuple(old[record.id] - set(record.company_ids.ids))) for record in self]
        removed = [(farm, companies) for farm, companies in removed if companies]
        if not removed:
            return
        self.env.cr.execute('''SELECT source.relname, ref.attname
            FROM pg_constraint fk
            JOIN pg_class source ON source.oid=fk.conrelid
            JOIN pg_attribute ref ON ref.attrelid=source.oid AND ref.attnum=fk.conkey[1]
            JOIN pg_attribute company ON company.attrelid=source.oid AND company.attname='company_id'
            WHERE fk.contype='f' AND fk.confrelid='step_fundo'::regclass
              AND cardinality(fk.conkey)=1 AND source.relnamespace='public'::regnamespace
              AND NOT company.attisdropped''')
        for table, column in self.env.cr.fetchall():
            for farm, companies in removed:
                self.env.cr.execute(SQL('SELECT 1 FROM %s WHERE %s = %s AND company_id IN %s LIMIT 1',
                                        SQL.identifier(table), SQL.identifier(column), farm, companies))
                if self.env.cr.fetchone():
                    raise ValidationError(_('Una empresa utiliza este fundo en documentos existentes.'))
