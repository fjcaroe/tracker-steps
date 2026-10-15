from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class Process(models.Model):
    _inherit = 'step.packing.process.type'
    changes_commercial_producer = fields.Boolean(string='Cambio de productor comercial',
        help='Exige seleccionar productor comercial para cada tarja de destino del repaletizado.')


class Package(models.Model):
    _inherit = 'stock.quant.package'
    commercial_producer_id = fields.Many2one('res.partner', string='Productor comercial',
        domain="[('is_productor','=',True)]", copy=True,
        help='Productor que aparece en la tarja impresa. El productor y fundo de origen se conservan.')

    @api.constrains('commercial_producer_id', 'company_id')
    def _check_commercial_producer(self):
        for tag in self:
            partner = tag.commercial_producer_id
            company = tag.company_id or self.env.company
            if partner and (not partner.is_productor or partner.company_id and partner.company_id != company):
                raise ValidationError(_('Seleccione un productor del maestro de la empresa o compartido.'))

    def write(self, vals):
        if 'commercial_producer_id' in vals and any(tag.is_fruit_tag and
                tag.step_tag_state not in ('created', 'void') for tag in self):
            raise UserError(_('Una tarja validada conserva el productor comercial; use otro repaletizado.'))
        return super().write(vals)


class RepackLine(models.Model):
    _inherit = 'step.packing.repack.line'
    commercial_producer_id = fields.Many2one(related='target_package_id.commercial_producer_id',
        readonly=False, string='Productor comercial')


class Repack(models.Model):
    _inherit = 'step.packing.repack'

    def _check_repack(self):
        location = super()._check_repack()
        targets = self.line_ids.target_package_id
        if self.process_type_id.changes_commercial_producer:
            if any(not target.commercial_producer_id for target in targets):
                raise ValidationError(_('Seleccione el productor comercial en todas las tarjas que entran.'))
        else:
            for target in targets:
                sources = self.line_ids.filtered(lambda row: row.target_package_id == target).source_package_id
                inherited = sources.commercial_producer_id
                if len(inherited) > 1 or target.commercial_producer_id != inherited:
                    raise ValidationError(_('Para cambiar el productor comercial use el tipo de proceso Cambio Productor.'))
        for target in targets:
            target._check_commercial_producer()
            if target.commercial_producer_id.company_id and target.commercial_producer_id.company_id != self.company_id:
                raise ValidationError(_('El productor comercial debe pertenecer a la empresa del repaletizado.'))
        if self.process_type_id.company_id and self.process_type_id.company_id != self.company_id:
            raise ValidationError(_('El tipo de proceso debe pertenecer a la empresa del repaletizado.'))
        return location

    def action_prepare_distribution(self):
        result = super().action_prepare_distribution()
        if not self.process_type_id.changes_commercial_producer:
            producers = self.selected_source_ids.commercial_producer_id
            if len(producers) > 1:
                raise ValidationError(_('Separe las tarjas con distinto productor comercial o use Cambio Productor.'))
            self.target_tag_ids.commercial_producer_id = producers
        return result
