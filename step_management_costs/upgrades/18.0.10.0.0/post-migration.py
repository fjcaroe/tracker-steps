"""Fase 4 — migración idempotente a 18.0.10.0.0.

Agrega el servicio de períodos (sin tabla), la derivación de tareas semanales
(columnas nullable en `step_management_plan_line` y `step_management_plan`) y el
plan de cosecha (`step_management_harvest_plan*`, tablas creadas por el ORM).
Sin backfill destructivo; reejecutable sin efecto.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        UPDATE step_management_plan_line
           SET generated = FALSE
         WHERE generated IS NULL
    """)
    normalized = cr.rowcount
    if normalized:
        _logger.info(
            "18.0.10.0.0: %s tarea(s) de plan marcadas como no generadas.",
            normalized,
        )

    cr.execute("""
        SELECT count(*) FROM information_schema.tables
         WHERE table_name = 'step_management_harvest_plan'
    """)
    if cr.fetchone()[0]:
        cr.execute("SELECT count(*) FROM step_management_harvest_plan")
        plans = cr.fetchone()[0]
        _logger.info(
            "18.0.10.0.0: %s plan(es) de cosecha preservados.", plans,
        )
