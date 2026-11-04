from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv.expression import AND, OR


BOM_SCOPE_FIELDS = {
    'mrp.bom': 'step_applicable_company_ids',
    'mrp.bom.line': 'bom_id.step_applicable_company_ids',
    'mrp.bom.byproduct': 'bom_id.step_applicable_company_ids',
    'mrp.routing.workcenter': 'bom_id.step_applicable_company_ids',
}


class Rule(models.Model):
    _inherit = 'ir.rule'

    @api.model
    def _compute_domain(self, model_name, mode='read'):
        domain = super()._compute_domain(model_name, mode)
        field = BOM_SCOPE_FIELDS.get(model_name)
        if not field or self.env.su:
            return domain
        active = self.env.companies.ids
        if mode == 'read':
            scope = OR([[(field, '=', False)], [(field, 'in', active)]])
        else:
            scope = [(field, 'not any', [('id', 'not in', active)])]
        return AND([domain, scope])


class BillOfMaterials(models.Model):
    _inherit = 'mrp.bom'

    step_applicable_company_ids = fields.Many2many(
        'res.company', string='Compañías donde aplica', copy=True,
        help='Para una lista sin compañía propietaria, limita su uso a las compañías seleccionadas.',
    )

    @api.constrains('company_id', 'step_applicable_company_ids')
    def _check_step_applicable_companies(self):
        for bom in self.filtered('step_applicable_company_ids'):
            if bom.company_id:
                raise ValidationError('Deje vacía la compañía propietaria al seleccionar compañías de aplicación.')
            if bom.step_applicable_company_ids - self.env.companies:
                raise ValidationError('Active todas las compañías seleccionadas antes de guardar la lista.')

    @api.model
    def _bom_find_domain(self, products, picking_type=None, company_id=False, bom_type=False):
        domain = super()._bom_find_domain(products, picking_type, company_id, bom_type)
        company = company_id or self.env.context.get('company_id') or self.env.company.id
        return AND([domain, ['|', ('step_applicable_company_ids', '=', False),
                             ('step_applicable_company_ids', 'in', [company])]])

    def _check_step_bom_company(self, company):
        for bom in self:
            if ((bom.company_id and bom.company_id != company)
                    or (bom.step_applicable_company_ids and company not in bom.step_applicable_company_ids)):
                raise ValidationError('La lista de materiales no aplica a la compañía de la orden.')


class PackingOrder(models.Model):
    _inherit = 'step.packing.order'

    @api.constrains('company_id')
    def _check_step_order_bom_scope(self):
        self.line_ids._check_step_bom_scope()

    def action_validate(self):
        self.line_ids._check_step_bom_scope()
        return super().action_validate()

    def action_refresh_materials(self):
        self.line_ids._check_step_bom_scope()
        return super().action_refresh_materials()


class PackingOrderLine(models.Model):
    _inherit = 'step.packing.order.line'

    @api.constrains('bom_id', 'order_id')
    def _check_step_bom_scope(self):
        for line in self.filtered('bom_id'):
            line.bom_id._check_step_bom_company(line.order_id.company_id)


class PackingProduction(models.Model):
    _inherit = 'step.packing.production'

    @api.constrains('bom_id', 'company_id')
    def _check_step_bom_scope(self):
        for production in self.filtered('bom_id'):
            production.bom_id._check_step_bom_company(production.company_id)

    def _check_packing_tags(self):
        self._check_step_bom_scope()
        return super()._check_packing_tags()
