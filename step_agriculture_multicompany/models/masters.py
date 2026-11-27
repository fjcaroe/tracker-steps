from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Fundo(models.Model):
    # Retain the original model alias while the shared farm provider owns its fields.
    _inherit = 'step.fundo'


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


def check_document_masters(records, package_companies=None):
    targets = {'step.fundo', 'step.management.fruit.category', 'step.management.fruit.class',
               'step.management.fruit.quality', 'step.fruit.color', 'step.management.fruit.caliber'}
    for record in records:
        company = record.company_id or (package_companies or {}).get(record.id) or record.env.company
        for name, field in record._fields.items():
            if field.type == 'many2one' and field.comodel_name in targets:
                master = record[name]
                if master and company not in master.sudo().company_ids:
                    raise ValidationError(_(
                        'En %(document)s, el maestro «%(master)s» del campo «%(field)s» no está asignado a '
                        'la empresa «%(company)s». Revise «Empresas y sucursales» en ese maestro.',
                        document=record.display_name,
                        master=master.sudo().display_name,
                        field=record.fields_get([name], ['string'])[name]['string'],
                        company=company.display_name,
                    ))


class Package(models.Model):
    _inherit = 'stock.quant.package'

    @api.constrains('company_id', 'fundo_id', 'fruit_category_id', 'fruit_class_id', 'fruit_quality_id', 'fruit_caliber_id')
    def _check_agricultural_masters(self):
        # Inventory clears the package company when its final stock is consumed.
        # Keep validating against the OT or the last completed stock movement.
        empty_tags = self.filtered(lambda tag: tag.is_fruit_tag and not tag.company_id)
        companies = {tag.id: tag.step_packing_production_id.sudo().company_id
                     for tag in empty_tags if tag.step_packing_production_id}
        historical = set(empty_tags.ids) - companies.keys()
        if historical:
            moves = self.env['stock.move.line'].sudo().search([
                ('state', '=', 'done'), '|', ('package_id', 'in', list(historical)),
                ('result_package_id', 'in', list(historical)),
            ], order='date desc, id desc')
            for line in moves:
                for tag in line.package_id | line.result_package_id:
                    if tag.id in historical:
                        companies.setdefault(tag.id, line.company_id)
        check_document_masters(self, companies)


class Production(models.Model):
    _inherit = 'step.packing.production'

    @api.onchange('fruit_grower_id', 'company_id')
    def _onchange_producer_fundo(self):
        for production in self:
            fundos = self.env['step.fundo'].search([
                ('partner_id', '=', production.fruit_grower_id.id),
                ('company_ids', 'in', production.company_id.ids),
            ], order='id') if production.fruit_grower_id else self.env['step.fundo']
            if production.fruit_fundo_id not in fundos:
                production.fruit_fundo_id = fundos[:1]

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


class ShipmentLine(models.Model):
    _inherit = 'step.export.shipment.line'

    @api.constrains('quality_id', 'shipment_id')
    def _check_quality_company(self):
        for line in self:
            if line.quality_id and line.shipment_id.company_id not in line.quality_id.sudo().company_ids:
                raise ValidationError(_('La calidad debe estar asignada a la empresa del embarque.'))
