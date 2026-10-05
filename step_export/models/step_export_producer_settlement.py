"""Receiver integration for the independent producer settlement core."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.step_producers.migration_helpers import register_season_aliases


class ProducerSettlement(models.Model):
    _inherit = 'step.export.producer.settlement'
    receiver_settlement_id = fields.Many2one('step.export.receiver.settlement', string='Liquidación recibidor', ondelete='restrict')

    _sql_constraints = [('producer_receiver_unique', 'unique(receiver_settlement_id, producer_id)',
                         'El productor ya tiene una liquidación para este recibidor.')]

    @api.model
    def _register_export_aliases(self):
        register_season_aliases(self.env.cr)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('receiver_settlement_id'):
                source = self.env['step.export.receiver.settlement'].browse(vals['receiver_settlement_id'])
                vals.update({'company_id': source.company_id.id, 'date': source.date,
                             'season_id': source.season_id.id, 'species_id': source.species_id.id})
        return super().create(vals_list)

    def _check_settlement_source(self):
        super()._check_settlement_source()
        source = self.receiver_settlement_id
        if source:
            if source.state not in ('validated', 'accounted'):
                raise UserError(_('Primero valide la liquidación del recibidor.'))
            if (self.company_id != source.company_id or self.season_id != source.season_id or
                    self.species_id != source.species_id or self.date != source.date):
                raise ValidationError(_('La liquidación debe conservar empresa, temporada, especie y fecha del recibidor.'))
            if any(not line.tag_id for line in self.line_ids):
                raise ValidationError(_('La liquidación del recibidor requiere tarjas trazables.'))
        return True

    def write(self, vals):
        if 'receiver_settlement_id' in vals and any(row.state != 'draft' for row in self):
            raise UserError(_('La liquidación validada conserva su recibidor.'))
        return super().write(vals)
