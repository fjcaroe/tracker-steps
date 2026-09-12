"""Corte V2 C — migración idempotente a 18.0.17.0.0.

Nueva dependencia del manifiesto: `purchase` (ya instalada en toda base con
Compras habilitada; si una base no la tiene instalada, el propio mecanismo
de dependencias de Odoo la instala al actualizar este módulo — no requiere
acción de este script).

`step.management.stock.requirement.line` gana `committed_quantity`,
`net_to_buy` y `committed_purchase_line_ids`: se recalculan en el próximo
«Calcular» de cada documento, no hay backfill de esquema.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT count(*) FROM information_schema.tables
         WHERE table_name = 'step_management_stock_requirement'
    """)
    if cr.fetchone()[0]:
        cr.execute("SELECT count(*) FROM step_management_stock_requirement WHERE state = 'computed'")
        computed = cr.fetchone()[0]
        _logger.info(
            "18.0.17.0.0: %s necesidad(es) de stock ya calculada(s); "
            "«comprometido»/«neto por comprar» quedan en 0 hasta el próximo "
            "«Calcular» (sin backfill de esquema).",
            computed,
        )
