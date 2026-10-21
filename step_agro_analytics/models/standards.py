from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LineStandard(models.Model):
    _name = 'step.packing.line.standard'
    _description = 'Estándar de kilos por hora de línea y especie'
    _rec_name = 'species_id'
    line_id = fields.Many2one('step.packing.line', required=True, ondelete='cascade', index=True)
    species_id = fields.Many2one('step.especie', string='Especie', required=True)
    company_id = fields.Many2one(related='line_id.company_id', store=True, string='Empresa')
    kg_hour = fields.Float(string='Estándar kg/h', required=True)
    _sql_constraints = [
        ('line_species_unique', 'unique(line_id,species_id)', 'Ya existe un estándar para esta línea y especie.'),
        ('positive_standard', 'check(kg_hour > 0)', 'El estándar debe ser mayor que cero.'),
    ]


class PackingLine(models.Model):
    _inherit = 'step.packing.line'
    standard_ids = fields.One2many('step.packing.line.standard', 'line_id', string='Estándares por especie')


class Production(models.Model):
    _inherit = 'step.packing.production'
    standard_kg_hour = fields.Float(copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'standard_kg_hour' not in vals and vals.get('step_packing_line_id') and vals.get('fruit_species_id'):
                line = self.env['step.packing.line'].browse(vals['step_packing_line_id'])
                company_id = vals.get('company_id') or self.env.company.id
                if line.company_id and line.company_id.id != company_id:
                    raise ValidationError(_('La línea pertenece a otra empresa.'))
                standard = self.env['step.packing.line.standard'].search([
                    ('line_id', '=', line.id), ('species_id', '=', vals['fruit_species_id'])], limit=1)
                if standard:
                    vals['standard_kg_hour'] = standard.kg_hour
        return super().create(vals_list)

    @api.onchange('step_packing_line_id', 'fruit_species_id')
    def _onchange_analytics_standard(self):
        for production in self:
            if production.state == 'created':
                standard = self.env['step.packing.line.standard'].search([
                    ('line_id', '=', production.step_packing_line_id.id),
                    ('species_id', '=', production.fruit_species_id.id)], limit=1)
                production.standard_kg_hour = standard.kg_hour if standard else 0
