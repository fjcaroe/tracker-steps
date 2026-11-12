from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.step_export_branch_consolidation.models import branch_companies


class Guide(models.Model):
    _inherit = 'step.dispatch.guide'

    step_shipment_company_id = fields.Many2one('res.company', compute='_compute_shipment_company')

    @api.depends('company_id')
    @api.depends_context('uid')
    def _compute_shipment_company(self):
        for guide in self:
            guide.step_shipment_company_id = guide.company_id.root_id & self.env.user.company_ids

    def _with_shipment_companies(self):
        self.ensure_one()
        companies = branch_companies(self.env, self.company_id)
        if not self.step_shipment_company_id:
            raise AccessError(_('El usuario necesita acceso a la empresa matriz para seleccionar un embarque.'))
        return self.with_context(allowed_company_ids=companies.ids)

    def _validated_shipment(self, shipment_id):
        self.ensure_one()
        domain = [('id', '=', shipment_id), ('company_id', '=', self.step_shipment_company_id.id),
                  ('state', '=', 'validated')]
        shipment = self.env['step.export.export'].search(domain, limit=1)
        if shipment:
            self.env.cr.execute('SELECT id FROM step_export_export WHERE id = %s FOR UPDATE', [shipment.id])
            shipment.invalidate_recordset(['state', 'company_id'])
            if shipment.state == 'validated' and shipment.company_id == self.step_shipment_company_id:
                return shipment
        raise ValidationError(_('Seleccione un embarque validado de la empresa matriz.'))

    @api.depends('step_export_shipment_ids', 'company_id', 'dispatch_type_id.step_recipient_kind')
    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_export_shipment(self):
        branch_guides = self.filtered(lambda guide: guide.step_recipient_kind == 'shipment')
        super(Guide, self - branch_guides)._compute_export_shipment()
        for guide in branch_guides:
            shipments = (guide._with_shipment_companies().step_export_shipment_ids
                         if guide.step_shipment_company_id and guide.company_id in self.env.user.company_ids
                         else self.env['step.export.export'])
            guide.step_export_shipment_id = shipments if len(shipments) == 1 else False

    def _inverse_export_shipment(self):
        branch_guides = self.filtered(lambda guide: guide.step_recipient_kind == 'shipment')
        super(Guide, self - branch_guides)._inverse_export_shipment()
        for guide in branch_guides.sorted('id'):
            target_id = guide.step_export_shipment_id.id
            self.env.cr.execute('SELECT id FROM step_dispatch_guide WHERE id = %s FOR UPDATE', [guide.id])
            scoped = guide._with_shipment_companies()
            target = scoped._validated_shipment(target_id) if target_id else scoped.env['step.export.export']
            previous = scoped.env['step.export.export'].search([('dispatch_guide_ids', 'in', guide.ids)])
            removed = previous - target
            if removed:
                if scoped.env['step.export.packing.list'].search_count([('guide_id', '=', guide.id)], limit=1):
                    raise ValidationError(_('La guía tiene un Packing List; no cambie su embarque.'))
                removed.write({'dispatch_guide_ids': [Command.unlink(guide.id)]})
            if target - previous:
                target.write({'dispatch_guide_ids': [Command.link(guide.id)]})

    @api.model_create_multi
    def create(self, values):
        guides = super().create(values)
        for guide, vals in zip(guides, values):
            if 'step_export_shipment_ids' in vals and guide.step_recipient_kind == 'shipment':
                raise ValidationError(_('Use el campo Embarque para vincular la guía.'))
        return guides

    def write(self, values):
        if {'company_id', 'dispatch_type_id', 'step_export_shipment_ids'} & values.keys():
            kinds = self.env['step.freight.dispatch.type']
            new_type = kinds.browse(values.get('dispatch_type_id'))
            for guide in self:
                if guide.step_recipient_kind != 'shipment' and new_type.step_recipient_kind != 'shipment':
                    continue
                if 'step_export_shipment_ids' in values:
                    raise ValidationError(_('Use el campo Embarque para vincular la guía.'))
                source_changed = ('company_id' in values and values['company_id'] != guide.company_id.id
                                  or 'dispatch_type_id' in values and new_type != guide.dispatch_type_id)
                if source_changed and guide.sudo().step_export_shipment_ids:
                    raise ValidationError(_('Quite el embarque antes de cambiar la empresa o el tipo de despacho.'))
        return super().write(values)


class PackingList(models.Model):
    _inherit = 'step.export.packing.list'

    step_dispatch_branch_id = fields.Many2one(related='guide_id.company_id', string='Sucursal del despacho')
