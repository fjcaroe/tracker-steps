# -*- coding: utf-8 -*-
"""Respaldo inicial de restricciones al instalar el módulo.

Es idempotente: se apoya en la clave única (modelo, aplicación, cuartel), de
modo que reinstalar o reejecutar el hook no duplica registros.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def post_init_hook(env_or_cr, registry=None):
    env = env_or_cr if isinstance(env_or_cr, api.Environment) else api.Environment(
        env_or_cr, SUPERUSER_ID, {}
    )
    restrictions = env["step.phyto.restriction"].refresh()
    _logger.info(
        "step_agro_traceability: %s restricciones derivadas de las aplicaciones existentes.",
        len(restrictions),
    )
