from odoo.exceptions import ValidationError
from odoo import _


def post_init_hook(env):
    tags = env['stock.quant.package'].search([
        ('is_fruit_tag', '=', True), ('step_tag_kind', 'in', ['E', 'N']),
        ('step_packing_production_id', '!=', False)])
    for tag in tags:
        company = tag.step_packing_production_id.company_id
        if (tag.company_id and tag.company_id != company or
                any(q.company_id != company for q in tag.quant_ids)):
            raise ValidationError(_('Revise la compañía de las tarjas resultantes antes de instalar.'))
        # Preserve location, IDs, weights, states and all stock history.
        if not tag.company_id:
            env.cr.execute('UPDATE stock_quant_package SET company_id=%s WHERE id=%s AND company_id IS NULL', [company.id, tag.id])
            tag.invalidate_recordset(['company_id'])
    env.flush_all()
