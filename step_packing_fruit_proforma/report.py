"""Read immutable proforma annex rows without sending or creating documents."""
from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import format_amount, formatLang


class FruitProformaReport(models.AbstractModel):
    _name = 'report.step_packing_fruit_proforma.report_fruit_proforma'
    _description = 'Proforma mensual de compra de fruta'

    @staticmethod
    def _guide_text(value):
        if isinstance(value, str):
            return value
        if not value:
            return ''
        if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
            return ', '.join(value)
        raise UserError(_('El anexo de la proforma contiene una referencia de guía inválida.'))

    def _annex_rows(self, document):
        rows = []
        for line in document.order_line.filtered(lambda item: not item.display_type):
            for source in line.step_fruit_source_rows or []:
                if not isinstance(source, dict):
                    raise UserError(_('El anexo de la proforma contiene una fila inválida.'))
                row = dict(source)
                row['receipt_guides'] = self._guide_text(row.get('receipt_guides'))
                rows.append(row)
        return rows

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['purchase.order'].browse(docids).exists()
        docs.check_access('read')
        if not docs or any(not doc.step_fruit_proforma for doc in docs):
            raise UserError(_('Este informe corresponde únicamente a proformas de compra de fruta.'))
        # Chilean fiscal references and Spanish labels use the same locale.
        language = 'es_CL' if self.env['res.lang'].search_count([('code', '=', 'es_CL'), ('active', '=', True)]) else self.env.lang
        localized = self.with_context(lang=language)
        docs = docs.with_context(lang=language)
        return {
            'doc_ids': docs.ids, 'doc_model': 'purchase.order', 'docs': docs,
            'annex_by_document': {doc.id: localized._annex_rows(doc) for doc in docs},
            'format_quantity': lambda number: formatLang(localized.env, number or 0, digits=4),
            'format_price': lambda number: formatLang(localized.env, number or 0, digits=12).rstrip('0').rstrip(',.') ,
            'format_money': lambda number, currency: format_amount(localized.env, number or 0, currency),
        }
