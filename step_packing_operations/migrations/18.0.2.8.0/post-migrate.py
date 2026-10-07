"""Link historical OT outputs without replacing packages or their stock."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute('''UPDATE step_export_stock_reservation r SET sales_program_id=o.sales_program_id
                  FROM step_packing_order o WHERE r.step_packing_order_id=o.id
                  AND o.sales_program_id IS NOT NULL AND r.sales_program_id IS NULL''')
    for ot in env['step.packing.production'].search([]):
        products = ot.step_packing_input_tag_ids.step_tag_line_ids.product_id
        if len(products) == 1:
            cr.execute('UPDATE step_packing_production SET raw_product_id=%s WHERE id=%s', [products.id, ot.id])
        for tag in ot.step_packing_output_tag_ids:
            origins = env['step.packing.production'].search([('step_packing_output_tag_ids', 'in', tag.id)])
            if len(origins) == 1:
                cr.execute('UPDATE stock_quant_package SET step_packing_production_id=%s WHERE id=%s', [ot.id, tag.id])
