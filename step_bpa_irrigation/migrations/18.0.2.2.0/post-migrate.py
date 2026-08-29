# -*- coding: utf-8 -*-
"""Recompone el nombre de Horas Máquina incorporando el segmento OT_BPA.

step_machinery ya asignó el Número OT y recompuso los nombres, pero en ese
momento la extensión BPA todavía no estaba en el registro. Esta pasada, también
idempotente, vuelve a componer el nombre ya con el folio de la OT-BPA.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Usage = env["step.hrs.machinery"].with_context(active_test=False)
    records = Usage.search([
        ("state", "not in", ("costed", "accounted")),
        ("invoice_id", "=", False),
    ])
    records._sync_composed_name()
    linked = len(records.filtered("bpa_order_id"))
    _logger.info(
        "BPA 18.0.2.2.0: %s registros de maquinaria revisados, %s con OT-BPA vinculada.",
        len(records), linked,
    )
