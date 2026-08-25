"""Renombra el perfil semilla del proveedor a la marca Steps.

El tablero de Nómina muestra el nombre del perfil en una píldora del hero, de
modo que la marca del proveedor quedaba a la vista del visitante. El perfil
lleva `noupdate="1"`, así que el cambio del XML no alcanza a las bases ya
instaladas y hay que aplicarlo aquí.

Sólo se renombra si el perfil conserva el nombre semilla: si el cliente lo
personalizó, su nombre manda.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

PREVIOUS = "SimpleDigital"
CURRENT = "Steps"


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    profile = env.ref(
        "step_hr_remuneration_book.profile_simpledigital",
        raise_if_not_found=False,
    )
    if not profile:
        return
    if (profile.name or "").strip() == PREVIOUS:
        profile.name = CURRENT
        _logger.info(
            "Libro de Remuneraciones: perfil renombrado a %s.", CURRENT)
    else:
        _logger.info(
            "Libro de Remuneraciones: el perfil tiene nombre propio (%s); "
            "no se toca.", profile.name)
