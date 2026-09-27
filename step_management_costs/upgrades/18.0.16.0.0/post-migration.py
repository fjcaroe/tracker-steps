"""Corte V2 B — migración idempotente a 18.0.16.0.0.

`step.management.historical.cost` gana campos nuevos, todos opcionales
(`dataset_kind`, `season`, `year`, `month`, etiquetas de archivo, montos
origen); los registros manuales previos a este corte quedan con
`dataset_kind` vacío y siguen funcionando exactamente igual (comparación
pareada `budget_amount`/`actual_amount`). Sin backfill de esquema.

`step.management.historical.template.version(.import.batch/.line)` son
modelos enteramente nuevos. Las dos versiones de plantilla vigentes
(presupuesto y real) se cargan por `data/historical_template_versions.xml`,
no por este script.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT count(*) FROM information_schema.tables
         WHERE table_name = 'step_management_historical_cost'
    """)
    if cr.fetchone()[0]:
        cr.execute("""
            SELECT count(*) FROM step_management_historical_cost
             WHERE dataset_kind IS NULL
        """)
        legacy = cr.fetchone()[0]
        _logger.info(
            "18.0.16.0.0: %s registro(s) manual(es) de costo histórico "
            "preservado(s) sin `dataset_kind` (comportamiento previo a V2 B, "
            "sin cambios).",
            legacy,
        )
