# -*- coding: utf-8 -*-
"""Homologa el catálogo de conceptos de maquinaria y su configuración contable.

Toda la lógica vive en `type.service.machinery._ensure_canonical_catalog()`
para poder ejecutarla también desde el hook de instalación y desde las
pruebas. El script es idempotente: repetirlo no duplica conceptos, no
reasigna cuentas ya correctas y no toca las relaciones existentes.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Service = env["type.service.machinery"].sudo()

    before = Service.search([])
    _logger.info(
        "Maquinaria 18.0.21.0.0: antes -> %s conceptos (%s), %s con cuenta de cargo, "
        "%s con cuenta de abono.",
        len(before), sorted(filter(None, before.mapped("cod"))),
        len(before.filtered("cargo_account_id")), len(before.filtered("abono_account_id")),
    )

    report = Service._ensure_canonical_catalog()

    env.invalidate_all()
    after = Service.search([])
    _logger.info(
        "Maquinaria 18.0.21.0.0: después -> %s conceptos (%s), %s con cuenta de cargo, "
        "%s con cuenta de abono.",
        len(after), sorted(filter(None, after.mapped("cod"))),
        len(after.filtered("cargo_account_id")), len(after.filtered("abono_account_id")),
    )
    for key in ("conceptos_normalizados", "conceptos_creados", "cuentas_creadas",
                "cuentas_reutilizadas", "relaciones_asignadas", "diario_cuentas_agregadas"):
        if report.get(key):
            _logger.info("Maquinaria 18.0.21.0.0 | %s: %s", key, report[key])
    _logger.info("Maquinaria 18.0.21.0.0 | diario final: %s", report.get("diario"))
