"""Populate document links from existing shipment relations, preserving snapshots.

Only reuse canonical relations. Unlinked or ambiguous imported text stays visible
as read-only history; it is never resolved by an approximate name match.
"""
import logging
from psycopg2 import sql
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    model = env['stock.quant.package']
    linked = model.search([('is_fruit_tag', '=', True), ('step_export_shipment_ids', '!=', False)])
    count = 0
    for tag in linked:
        shipments = tag.step_export_shipment_ids.filtered(lambda row: row.company_id == (tag.company_id or env.company))
        documents = {
            'step_guide_ids': shipments.dispatch_guide_ids,
            'step_invoice_ids': shipments.invoice_ids,
            'step_dus_shipment_ids': shipments.filtered('dus_folio'),
            'step_bl_shipment_ids': shipments.filtered('bl_folio'),
        }
        for name, records in documents.items():
            field = model._fields[name]
            for record in records:
                cr.execute(sql.SQL('INSERT INTO {} ({},{}) VALUES (%s,%s) ON CONFLICT DO NOTHING').format(
                    sql.Identifier(field.relation), sql.Identifier(field.column1), sql.Identifier(field.column2)),
                    [tag.id, record.id])
                count += cr.rowcount
    _logger.info('T55 document links migrated: %s; historical values preserved', count)
