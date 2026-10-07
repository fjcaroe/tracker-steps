"""Export sales selectors and optional APR presentation, without changing APR data."""
from copy import deepcopy

from lxml import etree
from odoo import api, fields, models
from odoo.osv import expression

APR_CONFIGURATION = ('product_fijo', 'product_consu')
APR_FIELDS = ('cod_medidor', 'sector_apr', 'carga_type', 'p_desde', 'p_hasta',
              'anterior_apr', 'actual_apr', 'consumo_apr')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    step_export_sale = fields.Boolean(string='Nota de exportación', copy=True)
    step_export_sale_context = fields.Boolean(compute='_compute_export_sale', string='Operación de exportación')
    step_apr_configured = fields.Boolean(compute='_compute_apr_configured', string='APR configurado')

    @api.depends('step_export_sale', 'step_export_sales_program_id', 'step_export_shipment_id')
    def _compute_export_sale(self):
        for order in self:
            order.step_export_sale_context = bool(order.step_export_sale or order.step_export_sales_program_id or order.step_export_shipment_id)

    @api.depends(lambda model: ['company_id'] + [
        'company_id.' + name for name in APR_CONFIGURATION if name in model.env['res.company']._fields])
    def _compute_apr_configured(self):
        for order in self:
            company = order.company_id
            order.step_apr_configured = bool(company and any(
                company[name] for name in APR_CONFIGURATION if name in company._fields))

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != 'form':
            return arch, view
        arch = deepcopy(arch)
        sheet = arch.find('sheet')
        if sheet is None:
            return arch, view
        for name in ('step_export_sale', 'step_export_sale_context', 'step_apr_configured'):
            if not arch.xpath(".//field[@name='%s']" % name):
                sheet.insert(0, etree.Element('field', name=name, invisible='1'))
        for node in arch.xpath('.//field'):
            if node.get('name') in APR_FIELDS:
                existing = node.get('invisible', 'False')
                node.set('invisible', '(%s) or not step_apr_configured' % existing)
        selectors = arch.xpath(".//field[@name='order_line']//field[@name='product_id' or @name='product_template_id']")
        for node in selectors:
            if node.get('domain') is not None or node.get('widget') in ('sol_product_many2one', 'many2one_barcode'):
                domain = node.get('domain', "[('sale_ok', '=', True)]")
                node.set('domain', "(%s) + ([('step_export_enabled', '=', True)] if parent.step_export_sale_context else [])" % domain)
        return arch, view

    def _get_product_catalog_domain(self):
        domain = super()._get_product_catalog_domain()
        if self.step_export_sale_context:
            domain = expression.AND([domain, [('step_export_enabled', '=', True)]])
        return domain
