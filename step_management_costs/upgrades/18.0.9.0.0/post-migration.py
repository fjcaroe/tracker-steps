"""Fase 3, corte 3 — migración idempotente a 18.0.9.0.0.

Sólo agrega la carga Excel de estimación (`step_management_estimation_import*`,
tablas creadas por el ORM) y la columna nullable
`step_management_estimation.import_id`. No hay datos que backfillear; se deja
evidencia del upgrade. Reejecutable sin efecto.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT count(*) FROM information_schema.tables
         WHERE table_name = 'step_management_estimation_import'
    """)
    if not cr.fetchone()[0]:
        return
    cr.execute("SELECT count(*) FROM step_management_estimation_import")
    imports = cr.fetchone()[0]
    cr.execute("""
        SELECT count(*) FROM step_management_estimation WHERE import_id IS NOT NULL
    """)
    linked = cr.fetchone()[0]
    _logger.info(
        "18.0.9.0.0: %s carga(s) Excel de estimación; %s estimación(es) con "
        "carga de origen preservadas.", imports, linked,
    )
