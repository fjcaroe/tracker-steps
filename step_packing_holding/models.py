from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.step_export_branch_consolidation.models import branch_companies
from odoo.tools.safe_eval import safe_eval


class Actions(models.Model):
    _inherit = 'ir.actions.act_window'

    def _get_action_dict(self):
        result = super()._get_action_dict()
        if self.res_model in ('step.packing.order', 'step.packing.production', 'step.dispatch.guide', 'step.export.dispatch.order'):
            previous = result.get('context') or {}
            context = safe_eval(previous, dict(self.env.context, uid=self.env.uid)) if isinstance(previous, str) else dict(previous)
            companies = branch_companies(self.env, self.env.company)
            context['allowed_company_ids'] = companies.ids
            result['context'] = context
        return result


class Order(models.Model):
    _inherit = 'step.packing.order'

    branch_company_id = fields.Many2one('res.company', related='company_id', readonly=False, string='Sucursal')
    holding_company_ids = fields.Many2many('res.company', compute='_compute_holding_companies')
    holding_program_company_ids = fields.Many2many('res.company', compute='_compute_holding_program_companies')
    sales_program_id = fields.Many2one(check_company=False, domain="[('company_id','in',holding_program_company_ids)]")

    @api.depends('company_id')
    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_holding_program_companies(self):
        for order in self:
            order.holding_program_company_ids = (order.company_id | order.company_id.root_id) & self.env.companies

    @api.constrains('company_id', 'sales_program_id')
    def _check_holding_program(self):
        for order in self:
            if order.sales_program_id:
                order.sales_program_id.check_access('read')
                if order.sales_program_id.company_id not in ((order.company_id | order.company_id.root_id) & self.env.companies):
                    raise ValidationError(_('Seleccione un programa de esta sucursal o de su matriz autorizada.'))

    @api.depends('company_id')
    @api.depends_context('uid', 'company')
    def _compute_holding_companies(self):
        for order in self:
            order.holding_company_ids = branch_companies(self.env, self.env.company)

    def _check_branch(self, company):
        if company not in branch_companies(self.env, self.env.company):
            raise AccessError(_('Seleccione una sucursal autorizada del mismo holding.'))

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for values in vals_list:
            values = dict(values)
            branch = values.pop('branch_company_id', False) or values.get('company_id') or self.env.company.id
            self._check_branch(self.env['res.company'].browse(branch))
            values['company_id'] = branch
            normalized.append(values)
        return super().create(normalized)

    def write(self, vals):
        vals = dict(vals)
        if vals.get('branch_company_id'):
            vals['company_id'] = vals.pop('branch_company_id')
        if vals.get('company_id'):
            target = self.env['res.company'].browse(vals['company_id'])
            self._check_branch(target)
            changed = self.filtered(lambda order: order.company_id != target)
            if any(order.state != 'draft' or order.production_ids for order in changed):
                raise UserError(_('La sucursal solo puede cambiar en una OP creada y sin órdenes de trabajo.'))
        else:
            changed = self.browse()
        result = super().write(vals)
        changed.filtered('material_need_ids').action_refresh_materials()
        return result


class OrderLine(models.Model):
    _inherit = 'step.packing.order.line'

    def action_create_production(self):
        self.ensure_one()
        return super(OrderLine, self.with_company(self.order_id.company_id)).action_create_production()


class Guide(models.Model):
    _inherit = 'step.dispatch.guide'

    holding_shipment_company_ids = fields.Many2many('res.company', compute='_compute_shipment_companies')
    step_export_shipment_id = fields.Many2one(domain="[('company_id','in',holding_shipment_company_ids)]")

    @api.depends('company_id')
    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_shipment_companies(self):
        for guide in self:
            guide.holding_shipment_company_ids = (guide.company_id | guide.company_id.root_id) & self.env.companies

    @api.constrains('step_export_shipment_id', 'company_id')
    def _check_holding_shipment(self):
        for guide in self:
            shipment = guide.step_export_shipment_id
            if shipment:
                shipment.check_access('read')
                if shipment.company_id not in ((guide.company_id | guide.company_id.root_id) & self.env.companies):
                    raise ValidationError(_('Seleccione un embarque de esta sucursal o de su matriz autorizada.'))

    def _inverse_export_shipment(self):
        self._check_holding_shipment()
        return super()._inverse_export_shipment()


class DispatchInstruction(models.Model):
    _inherit = 'step.export.dispatch.order'

    holding_shipment_company_ids = fields.Many2many('res.company', compute='_compute_shipment_companies')
    shipment_id = fields.Many2one(check_company=False, domain="[('company_id','in',holding_shipment_company_ids)]")

    @api.depends('company_id')
    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_shipment_companies(self):
        for instruction in self:
            instruction.holding_shipment_company_ids = (instruction.company_id | instruction.company_id.root_id) & self.env.companies

    @api.constrains('pallets_per_truck', 'shipment_id', 'company_id')
    def _check_instruction(self):
        for instruction in self:
            if instruction.pallets_per_truck <= 0:
                raise ValidationError(_('Pallets por camión debe ser positivo.'))
            if instruction.shipment_id:
                instruction.shipment_id.check_access('read')
                if instruction.shipment_id.company_id not in ((instruction.company_id | instruction.company_id.root_id) & self.env.companies):
                    raise ValidationError(_('Seleccione un embarque de esta sucursal o de su matriz autorizada.'))
