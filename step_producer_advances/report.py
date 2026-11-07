"""The supplied producer advance layout, using only frozen native PO sources."""
from datetime import timedelta

from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import format_amount, formatLang


class AdvanceReport(models.AbstractModel):
    _name = 'report.step_producer_advances.report_advance'
    _description = 'Proforma anticipo productor'

    def _advance_data(self, document):
        rows = []
        for line in document.order_line.filtered(lambda row: not row.display_type):
            detail = [dict(row) for row in line.step_fruit_source_rows or []]
            if not detail:
                raise UserError(_('La línea de anticipo requiere su anexo de fuentes.'))
            rounded = [document.currency_id.round(row['amount']) for row in detail]
            rounded[-1] += line.price_subtotal - sum(rounded)
            for row, amount in zip(detail, rounded):
                row['print_amount'] = amount
                row['receipt_guides'] = ', '.join(row.get('receipt_guides') or [])
                rows.append(row)
        monday = document.step_fruit_period_start - timedelta(days=document.step_fruit_period_start.weekday())
        weeks = [monday + timedelta(weeks=offset) for offset in
                 range((document.step_fruit_period_end - monday).days // 7 + 1)]
        received = sum(row['received_kg'] for row in rows)
        exported = sum(row['quantity'] for row in rows)
        partner = document.company_id.partner_id
        return {'rows': rows, 'fundos': ', '.join(sorted({row['fundo_name'] for row in rows})),
            'buyer_activity': partner.l10n_cl_activity_description if 'l10n_cl_activity_description' in partner._fields else '',
            'weeks': ', '.join('%s-S%02d' % day.isocalendar()[:2] for day in weeks),
            'received': received, 'exported': exported, 'ratio': exported / received if received else 0,
            'source_total': sum(row['source_amount'] for row in rows)}

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['purchase.order'].browse(docids).exists()
        docs.check_access('read')
        if not docs or any(not doc.step_advance_proforma for doc in docs):
            raise UserError(_('Este formato corresponde únicamente a anticipos de productores.'))
        lang = 'es_CL' if self.env['res.lang'].search_count([('code','=','es_CL'),('active','=',True)]) else self.env.lang
        localized = self.with_context(lang=lang)
        docs = docs.with_context(lang=lang)
        return {'docs': docs, 'doc_ids': docs.ids, 'doc_model': 'purchase.order',
            'data_by_doc': {doc.id: localized._advance_data(doc) for doc in docs},
            'number': lambda value: formatLang(localized.env, value or 0, digits=4),
            'price': lambda value: formatLang(localized.env, value or 0, digits=6).rstrip('0').rstrip(',.'),
            'percent': lambda value: formatLang(localized.env, 100 * (value or 0), digits=2),
            'money': lambda value, currency: format_amount(localized.env, value or 0, currency)}


class MonthlyReport(models.AbstractModel):
    _inherit = 'report.step_packing_fruit_proforma.report_fruit_proforma'

    def _get_report_values(self, docids, data=None):
        if self.env['purchase.order'].browse(docids).filtered('step_advance_proforma'):
            raise UserError(_('Use Imprimir anticipo para obtener el resumen y anexo de esta proforma.'))
        return super()._get_report_values(docids, data)
