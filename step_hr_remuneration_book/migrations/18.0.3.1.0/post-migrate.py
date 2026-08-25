"""Corrección de las reglas identificadoras del perfil SimpleDigital.

Validando la copia de trabajo contra datos reales apareció que hay compañías
sin ninguna línea `AFC_T` en el período —trabajadores sin seguro de cesantía—,
de modo que el perfil dejaba de detectarse justo donde tenía que funcionar. Se
sustituye `AFC_T` por el trío estructural `TOTAL_DSCTOS, GROSS, NET`, presente
en el 100 % de las liquidaciones observadas y suficiente para distinguir el
motor del proveedor.

El perfil semilla lleva `noupdate="1"`, así que sólo se corrige aquí y sólo si
el cliente no lo había cambiado.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.step_hr_remuneration_book.hooks import (
    activate_seed_profiles, ensure_group_implications,
)

_logger = logging.getLogger(__name__)

PREVIOUS = "TOTAL_DSCTOS,AFC_T,GROSS,NET"
CURRENT = "TOTAL_DSCTOS,GROSS,NET"


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    ensure_group_implications(env)

    profile = env.ref(
        "step_hr_remuneration_book.profile_simpledigital",
        raise_if_not_found=False,
    )
    if profile and (profile.detector_rule_codes or "").strip() == PREVIOUS:
        profile.detector_rule_codes = CURRENT
        _logger.info(
            "Libro de Remuneraciones: reglas identificadoras del perfil "
            "SimpleDigital actualizadas a %s.", CURRENT)
    elif profile:
        _logger.info(
            "Libro de Remuneraciones: el perfil SimpleDigital tiene reglas "
            "identificadoras propias; no se tocan.")

    activate_seed_profiles(env)
