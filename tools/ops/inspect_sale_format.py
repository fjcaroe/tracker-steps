"""Read report and commercial field metadata, excluding credentials/customer values."""
import json
from pathlib import Path

try:
    for model in ('sale.order', 'sale.order.line', 'res.company', 'res.partner.bank', 'res.bank', 'step.export.export'):
        print('FIELDS', model, json.dumps({name: {'label': field.string, 'type': field.type, 'relation': getattr(field, 'comodel_name', None)}
            for name, field in env[model]._fields.items() if any(word in name for word in ('export', 'ship', 'kg', 'kilo', 'box', 'caja', 'incoterm', 'bank', 'swift', 'aba', 'weight', 'freight', 'insurance'))}, ensure_ascii=False))
    for report in env['ir.actions.report'].search([('model', '=', 'sale.order')]):
        print('REPORT', report.id, report.name, report.report_name, report.get_external_id())
    for key in ('sale.report_saleorder_document', 'sale.report_saleorder', 'sale.report_saleorder_pro_forma'):
        view = env.ref(key)
        print('VIEW', key, view.arch_db)
        for child in env['ir.ui.view'].search([('inherit_id', '=', view.id)]):
            print('INHERIT', child.get_external_id(), child.priority, child.active, child.arch_db)
    print('COMPANIES', [(c.id, c.name, c.vat, bool(c.logo)) for c in env['res.company'].search([])])
    print('SALE_COUNT', env['sale.order'].search_count([]))
finally:
    env.cr.rollback()
