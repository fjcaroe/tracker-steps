"""Fase 3, corte 2 — migración idempotente a 18.0.8.0.0.

- Las tablas nuevas (`step_management_estimation*`) las crea el ORM.
- `step_management_cost_center.plants` se agrega de forma no destructiva con
  valor inicial 0; aquí sólo se normalizan filas heredadas que hubieran
  quedado NULL (idempotente: reejecutable sin efecto).
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        UPDATE step_management_cost_center
           SET plants = 0
         WHERE plants IS NULL
    """)
    normalized = cr.rowcount
    if normalized:
        _logger.info(
            "18.0.8.0.0: %s centro(s) de costo con plantas NULL normalizados a 0.",
            normalized,
        )

    cr.execute("""
        SELECT count(*) FROM information_schema.tables
         WHERE table_name = 'step_management_estimation'
    """)
    has_table = cr.fetchone()[0]
    if has_table:
        cr.execute("SELECT count(*) FROM step_management_estimation")
        estimations = cr.fetchone()[0]
        cr.execute("SELECT count(*) FROM step_management_estimation_version")
        versions = cr.fetchone()[0]
        _logger.info(
            "18.0.8.0.0: %s versión(es) y %s estimación(es) preservadas.",
            versions, estimations,
        )
