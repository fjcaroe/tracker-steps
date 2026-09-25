from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class Harvest(models.Model):
    _inherit = 'step.cosecha.registry'
    production_order_id = fields.Many2one('step.management.production.order', string='OP vigente',
        check_company=True, domain="[('company_id','=',company_id), ('state','=','authorized')]")

    @api.constrains('production_order_id','company_id')
    def _check_production_order(self):
        for record in self.filtered('production_order_id'):
            if record.production_order_id.company_id != record.company_id or record.production_order_id.state != 'authorized':
                raise ValidationError(_("Seleccione una OP vigente de la misma empresa."))

    def write(self, vals):
        if 'production_order_id' in vals and self.filtered('reception_picking_id'):
            raise UserError(_("La recepción ya fue generada; conserve su OP de origen."))
        return super().write(vals)

    def recibir_cosecha(self, reception_id=False):
        self._check_production_order()
        result = super().recibir_cosecha(reception_id=reception_id)
        for record in self:
            record.reception_picking_id.write({
                'production_order_id': record.production_order_id.id,
                'num_ot': record.mobile_work_order or record.name})
        return result
