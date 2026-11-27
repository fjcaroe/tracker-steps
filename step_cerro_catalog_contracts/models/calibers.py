"""Share existing inventory calibers without replacing their historical IDs."""
from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError


class CaliberGroup(models.Model):
    _name = 'step.management.caliber.group'
    _inherit = ['step.management.caliber.group', 'step.shared.agriculture.master']

    company_ids = fields.Many2many(
        'res.company', 'step_caliber_group_company_rel', 'master_id', 'company_id',
        string='Empresas y sucursales', required=True, default=lambda self: self.env.company)

    def write(self, vals):
        result = super().write(vals)
        if 'company_ids' in vals:
            calibers = self.env['step.management.fruit.caliber'].sudo().search([
                ('group_id', 'in', self.ids)])
            if any(c.company_ids - c.group_id.company_ids for c in calibers):
                raise ValidationError(_('El grupo debe conservar las empresas asignadas a sus calibres.'))
        return result


class FruitCaliber(models.Model):
    _name = 'step.management.fruit.caliber'
    _inherit = ['step.management.fruit.caliber', 'step.shared.agriculture.master']

    company_ids = fields.Many2many(
        'res.company', 'step_fruit_caliber_company_rel', 'master_id', 'company_id',
        string='Empresas y sucursales', required=True, default=lambda self: self.env.company,
        help='El calibre y su grupo estarán disponibles en estas empresas. Se conserva la empresa de origen.')

    def _share_group(self):
        # The assigned branches must also be able to read the classification.
        # Use the editor's permissions, never sudo to grant access to a company.
        for record in self:
            missing = record.company_ids - record.group_id.company_ids
            if missing:
                record.group_id.write({'company_ids': [Command.link(c.id) for c in missing]})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._share_group()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'company_ids', 'group_id'}.intersection(vals):
            self._share_group()
        return result
