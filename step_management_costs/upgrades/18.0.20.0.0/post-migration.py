"""Corte V2 F — comparativos, tablero y clasificación fuera de OP.

Todo lo nuevo son wizards `TransientModel` (sin tabla persistente que
migrar) y dos bloques agregados al tablero existente
(`get_management_dashboard`), calculados en vivo. `_season_start_month`
(`ir.config_parameter`, ya existente) es la única dependencia de
configuración: si no está seteado, sigue usando el valor por defecto
(mayo), igual que antes de este corte. Preflight informativo, sin cambios
de esquema."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT COUNT(*) FROM step_management_cost_center WHERE active")
    (centers,) = cr.fetchone()
    cr.execute("SELECT COUNT(*) FROM step_management_historical_cost")
    (costs,) = cr.fetchone()
    _logger.info(
        "step_management_costs %s: %s centro(s) activo(s), %s hecho(s) "
        "histórico(s) disponibles para el comparativo de temporada. Sin "
        "cambios de esquema.",
        version, centers, costs,
    )
