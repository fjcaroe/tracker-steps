"""Corte V2 A — migración idempotente a 18.0.15.0.0.

`step.management.harvest.plan.line` gana `center_id` (nuevo, opcional): los
planes de cosecha confirmados **antes** de este corte no lo tienen y no se
les asigna nada automáticamente (no hay fuente que lo demuestre). Este
script sólo es un **preflight de sólo lectura**: cuenta cuántas líneas de
planes ya confirmados quedan sin centro (evidencia para quien decida si
conviene regenerar una revisión), sin tocar nada. Reejecutable sin efecto.

`step.management.harvest.resource(.week)` son modelos enteramente nuevos:
sin backfill.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT count(*) FROM information_schema.columns
         WHERE table_name = 'step_management_harvest_plan_line'
           AND column_name = 'center_id'
    """)
    if not cr.fetchone()[0]:
        return

    cr.execute("""
        SELECT p.id, p.name, count(l.id)
          FROM step_management_harvest_plan p
          JOIN step_management_harvest_plan_line l ON l.harvest_plan_id = p.id
         WHERE p.state IN ('confirmed', 'superseded')
           AND l.center_id IS NULL
         GROUP BY p.id, p.name
    """)
    legacy = cr.fetchall()
    if legacy:
        _logger.warning(
            "18.0.15.0.0: %s plan(es) de cosecha confirmado(s)/reemplazado(s) "
            "con líneas sin centro (anteriores a este corte, sin cambios): %s",
            len(legacy),
            ", ".join("%s(#%s):%s líneas" % (name, pid, n) for pid, name, n in legacy),
        )
    else:
        _logger.info(
            "18.0.15.0.0: sin planes de cosecha confirmados con líneas sin centro."
        )
