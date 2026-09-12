# -*- coding: utf-8 -*-
"""Deja Temporada y Actividad con su cuenta analítica.

La corrección de la distribución analítica del comprobante de horas máquina
reparte por los tres planes de la contabilidad —Temporada, Centro de costos y
Actividad— usando la *cuenta analítica* de cada maestro. Los maestros que no
la tenían configurada dejaban el segmento fuera del apunte, así que aquí se
vinculan a la cuenta que ya existe o se crea la que falta.

Idempotente: una segunda pasada no crea ni reasigna nada.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.step_machinery.hooks import ensure_analytic_masters

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    report = ensure_analytic_masters(env)
    for key in ("vinculadas", "creadas", "sin_plan", "revisar"):
        if report.get(key):
            _logger.info("Maquinaria 18.0.22.0.0 | %s: %s", key, report[key])
    if not any(report.values()):
        _logger.info("Maquinaria 18.0.22.0.0: todos los maestros ya tenían cuenta analítica.")
