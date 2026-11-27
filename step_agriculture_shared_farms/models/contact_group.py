from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Partner(models.Model):
    _inherit = 'res.partner'

    step_contact_group_id = fields.Many2one(
        'res.partner', string='Grupo del contacto', ondelete='set null',
        index='btree_not_null', check_company=True,
        help='En la ficha Productor, identifica al productor padre.',
    )

    @api.constrains('step_contact_group_id', 'is_productor', 'company_id')
    def _check_step_contact_group(self):
        linked = self.filtered('step_contact_group_id')
        if not linked:
            return
        groups = linked.step_contact_group_id
        groups.check_access('read')
        linked._check_company(['step_contact_group_id'])
        if any(partner.is_productor and not partner.step_contact_group_id.is_productor for partner in linked):
            raise ValidationError(_('El grupo de un productor debe ser otro productor.'))
        if linked.sudo()._has_cycle('step_contact_group_id'):
            raise ValidationError(_('El grupo del contacto no puede formar un ciclo.'))


class Fundo(models.Model):
    _inherit = 'step.fundo'

    step_contact_group_id = fields.Many2one(
        'res.partner', string='Grupo del contacto', compute='_compute_step_contact_group',
    )

    @api.depends('partner_id.step_contact_group_id')
    @api.depends_context('uid', 'company')
    def _compute_step_contact_group(self):
        partners = self.env['res.partner'].with_context(active_test=False)
        producers = partners.search([('id', 'in', self.partner_id.ids)])
        groups = partners.search([('id', 'in', producers.step_contact_group_id.ids)])
        visible = {producer.id: producer.step_contact_group_id for producer in producers
                   if producer.step_contact_group_id in groups}
        for farm in self:
            farm.step_contact_group_id = visible.get(farm.partner_id.id, False)
