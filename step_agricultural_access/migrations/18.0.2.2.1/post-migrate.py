# -*- coding: utf-8 -*-
"""Repite la consolidación con el emparejamiento corregido.

La versión 18.0.2.2.0 comparaba los nombres de menú en el idioma de la sesión
de la migración (en_US) mientras los menús se mantienen en es_CL, así que
emparejaba ramas equivocadas. Ahora se comparan todas las traducciones y basta
con que una coincida. La rutina es idempotente: si el árbol ya está bien, no
hace nada.
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
        "Perfiles agrícolas 18.0.2.2.1: apps en el menú principal %s -> %s.", before, after)
    for key in ("pares", "raices_archivadas", "archivados_redundantes", "movidos"):
        if report.get(key):
            _logger.info("Perfiles agrícolas 18.0.2.2.1 | %s: %s", key, report[key])
