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


class Category(models.Model):
    _name = 'step.management.fruit.category'
    _inherit = ['step.management.fruit.category', 'step.shared.agriculture.master']
    company_ids = fields.Many2many('res.company', 'step_fruit_category_company_rel', 'master_id', 'company_id', string='Empresas y sucursales', required=True, default=lambda self: self.env.company)

    def write(self, vals):
        result = super().write(vals)
        if 'company_ids' in vals:
            self.env['step.management.fruit.class'].sudo().search([('category_id', 'in', self.ids)])._check_category_memberships()
        return result


class FruitClass(models.Model):
    _name = 'step.management.fruit.class'
    _inherit = ['step.management.fruit.class', 'step.shared.agriculture.master']
    company_ids = fields.Many2many('res.company', 'step_fruit_class_company_rel', 'master_id', 'company_id', string='Empresas y sucursales', required=True, default=lambda self: self.env.company)

    @api.constrains('company_ids', 'category_id')
    def _check_category_memberships(self):
        for record in self:
            if record.company_ids - record.category_id.company_ids:
                raise ValidationError(_('La categoría debe estar disponible en todas las empresas seleccionadas para la clase.'))


class Quality(models.Model):
    _name = 'step.management.fruit.quality'
    _inherit = ['step.management.fruit.quality', 'step.shared.agriculture.master']
    company_ids = fields.Many2many('res.company', 'step_fruit_quality_company_rel', 'master_id', 'company_id', string='Empresas y sucursales', required=True, default=lambda self: self.env.company)


class Color(models.Model):
    _name = 'step.fruit.color'
    _inherit = ['step.fruit.color', 'step.shared.agriculture.master']
    company_ids = fields.Many2many('res.company', 'step_fruit_color_company_rel', 'master_id', 'company_id', string='Empresas y sucursales', required=True, default=lambda self: self.env.company)


def check_document_masters(records):
    targets = {'step.fundo', 'step.management.fruit.category', 'step.management.fruit.class',
               'step.management.fruit.quality', 'step.fruit.color'}
    for record in records:
        company = record.company_id or record.env.company
        for name, field in record._fields.items():
            if field.type == 'many2one' and field.comodel_name in targets:
                master = record[name]
                if master and company not in master.sudo().company_ids:
                    raise ValidationError(_('El maestro seleccionado no está asignado a la empresa de la operación.'))


class Package(models.Model):
    _inherit = 'stock.quant.package'

    @api.constrains('company_id', 'fundo_id', 'fruit_category_id', 'fruit_class_id', 'fruit_quality_id')
    def _check_agricultural_masters(self):
        check_document_masters(self)


class Production(models.Model):
    _inherit = 'step.packing.production'

    @api.constrains('company_id', 'fruit_fundo_id')
    def _check_agricultural_masters(self):
        check_document_masters(self)


class Picking(models.Model):
    _inherit = 'stock.picking'

    @api.constrains('company_id', 'fruit_category_id', 'fruit_class_id')
    def _check_agricultural_masters(self):
        check_document_masters(self)


class Estimate(models.Model):
    _inherit = 'step.export.estimate'

    @api.constrains('company_id', 'fundo_id')
    def _check_agricultural_masters(self):
        check_document_masters(self)
