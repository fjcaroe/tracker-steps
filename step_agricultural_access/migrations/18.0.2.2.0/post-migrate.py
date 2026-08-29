# -*- coding: utf-8 -*-
"""Deja una sola entrada por aplicación en el menú principal.

Funde el árbol heredado de Studio dentro del árbol del módulo homónimo y
archiva la raíz de Studio ya vacía. Idempotente.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Menu = env["ir.ui.menu"].sudo().with_context(**{"ir.ui.menu.full_list": True})

    before = Menu.search_count([("parent_id", "=", False)])
    report = env["ir.ui.menu"]._consolidate_duplicated_apps()
    env.invalidate_all()
    after = Menu.search_count([("parent_id", "=", False)])

    _logger.info(
        "Perfiles agrícolas 18.0.2.2.0: apps en el menú principal %s -> %s.",
        before, after,
    )
    for key in ("pares", "raices_archivadas", "archivados_redundantes", "movidos"):
        if report.get(key):
            _logger.info("Perfiles agrícolas 18.0.2.2.0 | %s: %s", key, report[key])
