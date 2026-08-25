"""Cierre de la migración a 18.0.3.0.0.

* Restaura la asignación de perfil por empresa que guardó `pre-migrate`.
* Bloquea en borrador cualquier perfil creado por el cliente que usara el
  mecanismo eliminado (modelo/dominio/campo escritos desde la interfaz), con
  un mensaje que dice exactamente qué hay que rehacer.
* Valida y activa el resto.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.step_hr_remuneration_book.hooks import (
    activate_seed_profiles, ensure_group_implications,
)

_logger = logging.getLogger(__name__)

LEGACY_COLUMNS = ("model_name", "model_domain", "amount_field")


def _legacy_lines(cr):
    """Líneas que dependían del mecanismo eliminado, si la columna existe."""
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'step_remuneration_book_profile_line'
           AND column_name IN %s
        """,
        (LEGACY_COLUMNS,),
    )
    present = [row[0] for row in cr.fetchall()]
    if not present:
        return {}
    condition = " OR ".join(
        "%s IS NOT NULL AND %s <> ''" % (column, column) for column in present)
    cr.execute(
        "SELECT profile_id, array_agg(dt_code) "
        "  FROM step_remuneration_book_profile_line "
        " WHERE %s GROUP BY profile_id" % condition
    )
    return {row[0]: row[1] for row in cr.fetchall()}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Profile = env["step.remuneration.book.profile"]

    ensure_group_implications(env)

    # 1. Restaurar asignaciones por empresa.
    cr.execute(
        """
        SELECT table_name FROM information_schema.tables
         WHERE table_name = 'step_remuneration_book_profile_migration'
        """
    )
    if cr.fetchone():
        cr.execute(
            "SELECT company_id, profile_code "
            "  FROM step_remuneration_book_profile_migration"
        )
        for company_id, code in cr.fetchall():
            company = env["res.company"].browse(company_id).exists()
            profile = Profile.search([("code", "=", code)], limit=1)
            if company and profile:
                company.remuneration_book_profile_id = profile
        cr.execute("DROP TABLE step_remuneration_book_profile_migration")

    # 2. Perfiles del cliente que usaban el mecanismo eliminado.
    blocked = _legacy_lines(cr)
    for profile_id, dt_codes in blocked.items():
        profile = Profile.browse(profile_id).exists()
        if not profile:
            continue
        profile.write({
            "state": "draft",
            "validation_message": (
                "Los códigos DT %s se leían con un modelo y un dominio "
                "escritos desde la interfaz. Ese mecanismo se eliminó por "
                "seguridad. Vuelva a definirlos con un adaptador registrado "
                "(campo «Adaptador») antes de activar el perfil."
                % ", ".join(sorted(set(dt_codes)))
            ),
        })
        _logger.warning(
            "Libro de Remuneraciones: el perfil %s queda bloqueado hasta "
            "rehacer %s códigos con adaptadores.", profile.code, len(dt_codes))

    # 3. Perfiles semilla: validar y activar contra esta base.
    activate_seed_profiles(env)

    # 4. El resto de los perfiles: intentar validarlos sin forzarlos.
    others = Profile.search([
        ("id", "not in", list(blocked)),
        ("state", "=", "draft"),
    ])
    for profile in others:
        errors = profile.validation_errors()
        if errors:
            profile.validation_message = "\n".join(
                "• %s" % error for error in errors)
        else:
            profile.write({
                "state": "active",
                "validation_message": "Validación superada en la migración.",
            })
