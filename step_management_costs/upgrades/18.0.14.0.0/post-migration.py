"""Corte 2 — migración idempotente a 18.0.14.0.0.

La Orden de Producción (`step.management.production.order` + `.line`) es
enteramente nueva: no hay esquema previo que migrar ni backfill que hacer.
Este script sólo deja evidencia en el log (conteo de OP existentes, siempre
0 en la primera instalación de esta versión) y es reejecutable sin efecto.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT count(*) FROM information_schema.tables
         WHERE table_name = 'step_management_production_order'
    """)
    if cr.fetchone()[0]:
        cr.execute("SELECT count(*) FROM step_management_production_order")
        orders = cr.fetchone()[0]
        _logger.info(
            "18.0.14.0.0: %s Orden(es) de Producción preservada(s) (modelo "
            "nuevo, sin backfill de esquema).",
            orders,
        )
