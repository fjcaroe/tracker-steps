# -*- coding: utf-8 -*-
"""Refresca el Folio BPA almacenado y el nombre compuesto de Horas Máquina.

`bpa_folio` pasó a depender también del número y de la referencia de la OT-BPA.
Cambiar `@api.depends` no recalcula los valores ya almacenados, así que esta
pasada -idempotente- los vuelve a calcular y recompone los nombres de los
registros que todavía se pueden editar.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Usage = env["step.hrs.machinery"].sudo().with_context(active_test=False)

    todos = Usage.search([])
    if todos:
        env.add_to_compute(todos._fields["bpa_folio"], todos)
        todos.flush_recordset(["bpa_folio"])

    editables = todos.filtered(
        lambda record: record.state not in ("costed", "accounted") and not record.invoice_id)
    editables._sync_composed_name()

    _logger.info(
        "BPA 18.0.2.3.0: %s registros de maquinaria revisados, %s recompuestos, "
        "%s con OT-BPA vinculada.",
        len(todos), len(editables), len(todos.filtered("bpa_order_id")),
    )
