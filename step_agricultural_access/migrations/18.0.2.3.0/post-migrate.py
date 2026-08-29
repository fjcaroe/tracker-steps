# -*- coding: utf-8 -*-
"""Cierra las brechas de menús que quedaron de la consolidación anterior.

- Absorbe la app heredada "Gestión y Costos borrador" dentro de "Gestión y Costos".
- Archiva entradas que abren exactamente lo mismo con otro nombre (Fletes).
- Archiva los contenedores que la propia fusión dejó vacíos.

Idempotente: si ya está todo consolidado no hace nada.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Menu = env["ir.ui.menu"].sudo().with_context(**{"ir.ui.menu.full_list": True})
    before = Menu.search_count([("parent_id", "=", False), ("active", "=", True)])
    report = env["ir.ui.menu"]._consolidate_duplicated_apps()
    env.invalidate_all()
    after = Menu.search_count([("parent_id", "=", False), ("active", "=", True)])
    _logger.info(
        "Perfiles agrícolas 18.0.2.3.0: apps activas %s -> %s.", before, after)
    for key in ("pares", "raices_archivadas", "archivados_redundantes", "movidos"):
        if report.get(key):
            _logger.info("Perfiles agrícolas 18.0.2.3.0 | %s: %s", key, report[key])
