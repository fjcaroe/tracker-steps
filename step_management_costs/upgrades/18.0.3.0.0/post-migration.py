"""Post-migración a 18.0.3.0.0.

- Fija ``flow_type = 'cost'`` en los grupos existentes (defensivo; el default
  del campo ya lo hace al agregar la columna).
- Puebla ``flow_type`` (related stored) en líneas de presupuesto y de plantilla
  desde su grupo.
- Inicializa ``origin_type`` en presupuestos existentes.

Idempotente. Sin ``commit()`` manual, sin IDs numéricos hardcodeados.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        UPDATE step_management_budget_group
        SET flow_type = 'cost'
        WHERE flow_type IS NULL
    """)

    cr.execute("""
        UPDATE step_management_budget_line l
        SET flow_type = g.flow_type
        FROM step_management_budget_group g
        WHERE l.group_id = g.id AND l.flow_type IS DISTINCT FROM g.flow_type
    """)
    _logger.info("18.0.3.0.0: flow_type poblado en %s líneas de presupuesto.", cr.rowcount)

    cr.execute("""
        UPDATE step_management_budget_template_line l
        SET flow_type = g.flow_type
        FROM step_management_budget_group g
        WHERE l.group_id = g.id AND l.flow_type IS DISTINCT FROM g.flow_type
    """)
    _logger.info("18.0.3.0.0: flow_type poblado en %s indicadores de plantilla.", cr.rowcount)

    # origin_type: nuevo compute stored. Todos los presupuestos previos vienen de
    # plantilla (template_id era obligatorio antes de esta versión).
    cr.execute("""
        UPDATE step_management_operational_budget
        SET origin_type = CASE
            WHEN import_id IS NOT NULL THEN 'import'
            WHEN template_id IS NOT NULL THEN 'template'
            ELSE 'manual' END
        WHERE origin_type IS NULL
    """)
    _logger.info("18.0.3.0.0: origin_type inicializado en %s presupuestos.", cr.rowcount)
