from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Package(models.Model):
    _inherit = 'stock.quant.package'

    step_packing_company_id = fields.Many2one('res.company', readonly=True, copy=False)
    step_packing_duplicate_of_id = fields.Many2one(
        'stock.quant.package', string='Tarja vigente', readonly=True, copy=False, ondelete='restrict',
    )

    @api.depends('quant_ids.location_id', 'quant_ids.company_id', 'step_packing_company_id',
                 'step_packing_production_id.company_id', 'step_tag_kind', 'is_fruit_tag')
    def _compute_package_info(self):
        super()._compute_package_info()
        for tag in self.filtered('is_fruit_tag'):
            production = tag.step_packing_production_id
            company = production.company_id if production and tag.step_tag_kind in ('E', 'N') else tag.step_packing_company_id
            if company:
                if any(quant.company_id != company for quant in tag.quant_ids):
                    raise ValidationError(_('Las existencias de la tarja deben pertenecer a su compañía.'))
                tag.company_id = company

    def _fruit_tag_company(self, values, previous=False):
        order_id = values.get('step_packing_production_id', self.env.context.get('default_step_packing_production_id'))
        receipt_id = values.get('step_process_reception_id', self.env.context.get('default_step_process_reception_id'))
        origin = self.env['step.packing.production'].browse(order_id).company_id if order_id else False
        if receipt_id and not origin:
            origin = self.env['stock.picking'].browse(receipt_id).company_id
        supplied = self.env['res.company'].browse(values.get('company_id') or [])
        if origin and supplied and origin != supplied:
            raise ValidationError(_('La compañía de la tarja debe coincidir con su documento de origen.'))
        return origin or previous or supplied or self.env.company

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for values in vals_list:
            if values.get('is_fruit_tag', self.env.context.get('default_is_fruit_tag', False)):
                company = self._fruit_tag_company(values)
                values = dict(values, company_id=company.id, step_packing_company_id=company.id)
            prepared.append(values)
        return super().create(prepared)

    def write(self, values):
        if 'step_packing_company_id' in values:
            raise ValidationError(_('La compañía de origen de una tarja se asigna automáticamente.'))
        if 'company_id' in values:
            for tag in self.filtered('is_fruit_tag'):
                if not values['company_id'] or tag.company_id and tag.company_id.id != values['company_id']:
                    raise ValidationError(_('La compañía de una tarja de fruta debe conservarse.'))
        if values.get('is_fruit_tag'):
            changing = self.filtered(lambda tag: not tag.is_fruit_tag)
            for tag in changing:
                company = tag._fruit_tag_company(values, previous=tag.company_id)
                super(Package, tag).write(dict(values, company_id=company.id, step_packing_company_id=company.id))
            self -= changing
        return super().write(values) if self else True

    @api.constrains('step_packing_duplicate_of_id', 'step_tag_state')
    def _check_packing_duplicate_of(self):
        for tag in self.filtered('step_packing_duplicate_of_id'):
            target = tag.step_packing_duplicate_of_id
            if (tag == target or not target.is_fruit_tag or tag.step_tag_state != 'void'
                    or target.step_tag_state == 'void' or target.step_packing_duplicate_of_id
                    or not tag.step_packing_production_id
                    or tag.step_packing_production_id != target.step_packing_production_id):
                raise ValidationError(_('Una tarja repetida debe estar nula y apuntar a una tarja vigente de la misma OT.'))
