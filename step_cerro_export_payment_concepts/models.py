from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import SQL


COST = 'step.export.packaging.cost'
RULE = 'step_export.rule_export_packaging_cost_company'
STANDARD_COSTS = {'standard_cost_per_kg', 'standard_cost_per_box', 'standard_cost_per_pallet'}


class ExportPaymentConcept(models.Model):
    _name = 'step.export.payment.concept'
    _description = 'Concepto de Pago Productor'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Concepto de Pago Productor', required=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    code = fields.Char(string='Código')
    notes = fields.Html(string='Notas')
    date = fields.Date(string='Fecha')
    standard_cost_per_kg = fields.Float(string='Costo estándar por kg', digits=(16, 4))
    standard_cost_per_box = fields.Float(string='Costo estándar por caja', digits=(16, 4))
    standard_cost_per_pallet = fields.Float(string='Costo estándar por pallet', digits=(16, 4))

    def _has_valued_program(self):
        if not self:
            return False
        if COST in self.env:
            return bool(self.env[COST].search_count([('concept_id', 'in', self.ids), ('program_id.state', '=', 'valued')]))
        # The cost application may still be outside this registry. Its real
        # tables, model, grants and company rule remain in the restored graph.
        if not self.env.su and COST not in self.env['ir.model.access']._get_allowed_models('read'):
            raise AccessError(_('No tiene permiso para consultar costos de embalaje.'))
        rules = self.env['ir.rule']._get_rules(COST, 'read').sudo()
        scope = SQL('')
        if rules:
            original = self.env.ref(RULE).sudo()
            if rules != original or original.domain_force != "[('program_id.company_id','in',company_ids)]":
                raise ValidationError(_('Revise las reglas vigentes del programa de embalajes antes de modificar sus costos.'))
            scope = SQL('AND p.company_id IN %s', tuple(self.env.companies.ids))
        self.env.cr.execute(SQL("""SELECT 1 FROM step_export_packaging_cost c JOIN step_export_packaging_program p
            ON p.id=c.program_id WHERE c.concept_id IN %s AND p.state='valued' %s LIMIT 1""",
                                tuple(self.ids), scope))
        return bool(self.env.cr.fetchone())

    def write(self, vals):
        if STANDARD_COSTS.intersection(vals) and self._has_valued_program():
            raise UserError(_('El costo estándar ya se usó en un programa valorizado.'))
        return super().write(vals)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    step_export_payment_concept_id = fields.Many2one(
        'step.export.payment.concept', string='Concepto de liquidación')
