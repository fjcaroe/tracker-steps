"""Instalación inicial del puente de maquinaria: sólo campos nuevos, todos
opcionales (`machinery_vehicle_id`, `machinery_labor_id`,
`machinery_component_json`). No hay backfill posible ni necesario — el
detalle de presupuesto existente simplemente no tiene maquinaria asociada
hasta que un usuario la complete. Preflight de sólo lectura, informativo."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        "SELECT COUNT(*) FROM step_management_budget_line WHERE category = 'machinery'"
    )
    (count,) = cr.fetchone()
    _logger.info(
        "step_management_costs_machinery %s: %s línea(s) de categoría "
        "'machinery' ya existentes en el detalle de presupuesto, sin "
        "maquinaria asociada todavía (campo nuevo, opcional).",
        version, count,
    )
