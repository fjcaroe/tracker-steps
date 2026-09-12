"""Corte V2 E — refactor no destructivo de `_revision_line_commands()`.

`step.management.budget.line` no gana columnas nuevas en este corte del
núcleo: sólo se generaliza cómo `_create_revision()` copia sus campos a la
revisión (de una lista fija a `REVISION_LINE_FIELDS`, un conjunto que un
puente instalado al lado — p. ej. `step_management_costs_machinery` — puede
extender). Nada que migrar en filas existentes; preflight informativo.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT COUNT(*) FROM step_management_operational_budget")
    (count,) = cr.fetchone()
    _logger.info(
        "step_management_costs %s: %s presupuesto(s) existente(s); "
        "_revision_line_commands() generalizado, sin cambios de esquema.",
        version, count,
    )
