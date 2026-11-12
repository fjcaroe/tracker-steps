from odoo import _, api, Command, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.step_export_branch_consolidation.models import branch_companies


class Guide(models.Model):
    _inherit = 'step.dispatch.guide'

    _rec_names_search = ['name', 'external_folio']


class PackingList(models.Model):
    _inherit = 'step.export.packing.list'

    step_packing_company_ids = fields.Many2many('res.company', compute='_compute_packing_matrix')
    step_packing_shipment_domain = fields.Json(compute='_compute_packing_matrix')
    step_uses_guide_pallets = fields.Boolean(related='guide_id.step_is_shipment_dispatch')
    available_guide_ids = fields.Many2many(
        'step.dispatch.guide', related=False, compute='_compute_available_dispatches', compute_sudo=False)
    available_tag_ids = fields.Many2many(
        'stock.quant.package', related=False, compute='_compute_available_dispatches', compute_sudo=False)

    def _packing_scope(self):
        company = self.env.company
        return self.with_context(allowed_company_ids=branch_companies(self.env, company).ids)

    @api.depends_context('company', 'uid')
    def _compute_packing_matrix(self):
        company = self.env.company
        matrix = company.root_id & self.env.user.company_ids
        companies = branch_companies(self.env, company)
        for packing in self:
            packing.step_packing_company_ids = companies
            packing.step_packing_shipment_domain = (
                [('company_id', '=', matrix.id), ('state', '!=', 'draft')]
                if company.parent_id and matrix else [('id', '=', False)] if company.parent_id else [])

    @api.depends('shipment_id.dispatch_guide_ids', 'shipment_id.tag_ids', 'guide_id.state',
                 'guide_id.step_is_shipment_dispatch', 'guide_id.load_tag_ids')
    @api.depends_context('company', 'uid', 'allowed_company_ids')
    def _compute_available_dispatches(self):
        scoped = self._packing_scope()
        for packing, document in zip(self, scoped):
            shipment = document.shipment_id
            if not shipment or not shipment.has_access('read'):
                packing.available_guide_ids = False
                packing.available_tag_ids = False
                continue
            company = scoped.env.company
            guides = scoped.env['step.dispatch.guide'].search([
                ('id', 'in', shipment.dispatch_guide_ids.ids)])
            packing.available_guide_ids = guides.filtered(lambda guide: not guide.step_is_shipment_dispatch
                or (guide.state == 'confirmed' and (not company.parent_id or guide.company_id == company)))
            packing.available_tag_ids = (document.guide_id.load_tag_ids if document.step_uses_guide_pallets
                                         else shipment.tag_ids)

    @api.onchange('shipment_id')
    def _onchange_shipment_guide(self):
        if self.guide_id and self.guide_id not in self.available_guide_ids:
            self.guide_id = False
            self.tag_ids = [Command.clear()]

    @api.onchange('guide_id')
    def _onchange_guide_tags(self):
        super()._onchange_guide_tags()
        if self.step_uses_guide_pallets:
            self.tag_ids = [Command.set(self._packing_scope().guide_id.load_tag_ids.ids)]

    @api.model
    def _check_packing_selection(self, shipment, guide):
        if not shipment:
            raise ValidationError(_('Seleccione el embarque vinculado a la guía.'))
        shipment.check_access('read')
        guide.check_access('read')
        company = self.env.company
        if (guide.state != 'confirmed' or shipment.state == 'draft'
                or guide.company_id.root_id != shipment.company_id
                or guide.company_id.root_id != company.root_id
                or (company.parent_id and guide.company_id != company)
                or shipment not in guide.step_export_shipment_ids):
            raise ValidationError(_('Seleccione una guía confirmada de la sucursal, vinculada al embarque de su matriz.'))

    def _check_branch_packing_source(self):
        for packing in self:
            guide = packing.guide_id
            if not guide.step_is_shipment_dispatch:
                continue
            self._check_packing_selection(packing.shipment_id, guide)
            if not guide.load_tag_ids or packing.tag_ids != guide.load_tag_ids:
                raise ValidationError(_('El Packing List debe usar exactamente las tarjas de la guía confirmada.'))
            guide.load_tag_ids.check_access('read')
            if any(tag.company_id != guide.company_id for tag in guide.load_tag_ids):
                raise ValidationError(_('Las tarjas deben pertenecer a la sucursal que despachó la guía.'))

    @api.constrains('shipment_id', 'guide_id', 'tag_ids')
    def _check_links(self):
        shipment_packings = self.filtered('step_uses_guide_pallets')
        super(PackingList, self - shipment_packings)._check_links()
        shipment_packings._check_branch_packing_source()

    @api.model_create_multi
    def create(self, vals_list):
        scoped = self._packing_scope()
        prepared = [scoped._prepare_branch_packing(vals, vals.get('shipment_id')) for vals in vals_list]
        return super(PackingList, scoped).create(prepared).with_env(self.env)

    def write(self, vals):
        scoped = self._packing_scope()
        if vals.get('guide_id'):
            shipment_ids = scoped.shipment_id.ids
            if 'shipment_id' in vals or len(shipment_ids) == 1:
                vals = scoped._prepare_branch_packing(vals, vals.get('shipment_id', shipment_ids[0] if shipment_ids else False))
            else:
                for packing in scoped:
                    packing.write(vals)
                return True
        return super(PackingList, scoped).write(vals)

    def _prepare_branch_packing(self, vals, shipment_id):
        guide = self.env['step.dispatch.guide'].browse(vals.get('guide_id'))
        if guide and guide.step_is_shipment_dispatch:
            shipment = self.env['step.export.export'].browse(shipment_id)
            self._check_packing_selection(shipment, guide)
            if 'tag_ids' not in vals:
                return dict(vals, tag_ids=[Command.set(guide.load_tag_ids.ids)])
        return vals

    def web_read(self, specification):
        return super(PackingList, self._packing_scope()).web_read(specification)

    def action_export_excel(self):
        return super(PackingList, self._packing_scope()).action_export_excel()

    def action_print(self):
        scoped = self._packing_scope()
        action = super(PackingList, scoped).action_print()
        action['context'] = dict(action.get('context', {}), allowed_company_ids=scoped.env.companies.ids)
        return action
