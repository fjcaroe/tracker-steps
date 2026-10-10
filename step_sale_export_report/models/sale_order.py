from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Company(models.Model):
    _inherit = 'res.company'

    step_export_sale_format = fields.Boolean(string='Formato Nota de venta / Proforma exportación')
    step_export_bank_id = fields.Many2one('res.partner.bank', string='Cuenta para instrucciones de transferencia',
        domain="[('partner_id', '=', partner_id), '|', ('company_id', '=', False), ('company_id', '=', id)]")

    @api.constrains('step_export_bank_id', 'partner_id')
    def _check_export_bank(self):
        for company in self:
            bank = company.step_export_bank_id
            if bank and (bank.partner_id != company.partner_id or (bank.company_id and bank.company_id != company)):
                raise ValidationError(_('La cuenta debe pertenecer a la empresa del documento.'))


class Bank(models.Model):
    _inherit = 'res.bank'

    step_aba_routing = fields.Char(string='ABA / Routing number')


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    step_export_kg = fields.Float(string='Kilos', digits=(16, 3), help='Kilos netos correspondientes a esta línea.')
    step_export_boxes = fields.Float(string='Cajas', digits=(16, 2), help='Cantidad de cajas correspondiente a esta línea.')
    step_export_charge = fields.Selection([('product', 'Producto'), ('freight', 'Flete'), ('insurance', 'Seguro')],
        string='Detalle en Proforma', default='product', required=True)

    @api.constrains('step_export_kg', 'step_export_boxes')
    def _check_export_quantities(self):
        for line in self:
            if line.step_export_kg < 0 or line.step_export_boxes < 0:
                raise ValidationError(_('Kilos y cajas no pueden ser negativos.'))


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    step_export_sale_format = fields.Boolean(related='company_id.step_export_sale_format')

    def _step_export_report_values(self):
        self.ensure_one()
        lines = self._get_order_lines_to_report()
        items = lines.filtered(lambda line: not line.display_type)
        freight = sum(items.filtered(lambda line: line.step_export_charge == 'freight').mapped('price_subtotal'))
        insurance = sum(items.filtered(lambda line: line.step_export_charge == 'insurance').mapped('price_subtotal'))
        return {'lines': lines.filtered(lambda line: line.display_type or line.step_export_charge == 'product'),
                'subtotal': self.amount_untaxed - freight - insurance, 'freight': freight, 'insurance': insurance,
                'bank': self.company_id.step_export_bank_id,
                'incoterm': self.incoterm or self.step_export_shipment_id.incoterm_id}
