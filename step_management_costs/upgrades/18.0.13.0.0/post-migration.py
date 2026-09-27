"""Corte 1 post Fase 6 — migración idempotente a 18.0.13.0.0.

Sin backfill de esquema: los campos nuevos (`warehouse_id`,
`availability_metric`, `computed_at` en necesidades de stock; sin cambios de
esquema en programas) los completa el ORM al agregar las columnas. Este
script sólo es un **preflight de sólo lectura**: registra en el log los
programas fito/ferti existentes con problemas de coherencia de variedad
(R4, revisión post Corte 1: mezcla de centros con/sin variedad informada,
variedades distintas, o desacuerdo entre el encabezado y los centros — no
sólo "variedades mezcladas" como antes). No borra, no reinterpreta, no
corrige nada — es evidencia para revisión manual. Reejecutable sin efecto.
Usa la misma función de validación que el modelo (`_variety_issue`), para no
duplicar la regla entre el código y la migración.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    cr.execute("""
        SELECT count(*) FROM information_schema.tables
         WHERE table_name = 'step_management_crop_program'
    """)
    if cr.fetchone()[0]:
        from odoo.addons.step_management_costs.models.crop_program import (
            _variety_issue,
        )

        programs = env["step.management.crop.program"].sudo().with_context(
            active_test=False
        ).search([])
        issues = []
        for program in programs:
            issue = _variety_issue(program.center_ids, program.variety)
            if issue:
                issues.append("%s(#%s): %s" % (program.name, program.id, issue))
        if issues:
            _logger.warning(
                "18.0.13.0.0: %s programa(s) con problemas de coherencia de "
                "variedad (revisión manual, sin bloquear el upgrade):\n%s",
                len(issues), "\n".join(issues),
            )
        else:
            _logger.info(
                "18.0.13.0.0: sin problemas de coherencia de variedad en "
                "programas."
            )

    cr.execute("""
        SELECT count(*) FROM information_schema.tables
         WHERE table_name = 'step_management_stock_requirement'
    """)
    if cr.fetchone()[0]:
        cr.execute("SELECT count(*) FROM step_management_stock_requirement")
        requirements = cr.fetchone()[0]
        _logger.info(
            "18.0.13.0.0: %s consolidación(es) de necesidades de stock "
            "preservadas; el cruce con inventario se completa al recalcular.",
            requirements,
        )
