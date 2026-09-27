"""Fase 6 — migración idempotente a 18.0.12.0.0.

Sólo agrega la consolidación de necesidades de stock
(`step_management_stock_requirement*`, tablas creadas por el ORM). Sin backfill;
se deja evidencia del upgrade. Reejecutable sin efecto.
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
    if not cr.fetchone()[0]:
        return
    cr.execute("SELECT count(*) FROM step_management_stock_requirement")
    requirements = cr.fetchone()[0]
    _logger.info(
        "18.0.12.0.0: %s consolidación(es) de necesidades de stock preservadas.",
        requirements,
    )
