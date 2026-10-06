"""Populate the new species selector from the product master when available."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE step_producer_purchase_contract_product AS line
           SET species_id = template.step_export_species_id
          FROM product_product AS product
          JOIN product_template AS template ON template.id = product.product_tmpl_id
         WHERE line.product_id = product.id
           AND line.species_id IS NULL
           AND template.step_export_species_id IS NOT NULL
    """)
    _logger.info("T30: species populated on %s existing contract lines", cr.rowcount)
