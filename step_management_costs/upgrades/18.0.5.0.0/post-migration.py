"""Post-migración a 18.0.5.0.0.

- Inicializa ``budget_type`` en los presupuestos existentes. Todos los
  presupuestos previos a esta versión son «agrícolas» (se calculaban desde una
  plantilla por hectárea o desde la carga Excel del Anexo 1.6.2.1). El default
  del campo ya lo cubre al crear la columna; este UPDATE es defensivo e
  idempotente.

Sin ``commit()`` manual, sin IDs numéricos hardcodeados.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        UPDATE step_management_operational_budget
        SET budget_type = 'agricultural'
        WHERE budget_type IS NULL
    """)
    _logger.info(
        "18.0.5.0.0: budget_type inicializado en %s presupuestos.", cr.rowcount
    )
