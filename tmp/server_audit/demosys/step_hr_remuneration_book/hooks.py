"""Instalación honesta: implicaciones de grupo y activación de perfiles.

Dos cosas que no pueden quedarse en XML:

* Las implicaciones sobre grupos de otros módulos. Los grupos de `hr_payroll`
  están marcados `noupdate="1"` en su propio addon, de modo que un
  `<record id="hr_payroll....">` desde aquí se descarta **en silencio**: el
  permiso parecería concedido sin estarlo. Se aplican con el ORM, de forma
  idempotente, en cada instalación y actualización.
* La activación de los perfiles semilla. Un perfil no se marca validado por el
  hecho de que el módulo esté instalado: se valida contra la base real. Si un
  adaptador necesita un modelo que no está presente, el perfil queda en
  BORRADOR con un mensaje accionable y no puede usarse.
"""

import logging

_logger = logging.getLogger(__name__)

SEED_PROFILE_XML_IDS = (
    "step_hr_remuneration_book.profile_l10n_cl_extended",
    "step_hr_remuneration_book.profile_simpledigital",
)

#: `(grupo que recibe el permiso, grupo implicado)`.
GROUP_IMPLICATIONS = (
    ("hr_payroll.group_hr_payroll_manager",
     "step_hr_remuneration_book.group_remuneration_book_full"),
    ("base.group_system",
     "step_hr_remuneration_book.group_remuneration_book_technical"),
)


def ensure_group_implications(env):
    for holder_xml_id, implied_xml_id in GROUP_IMPLICATIONS:
        holder = env.ref(holder_xml_id, raise_if_not_found=False)
        implied = env.ref(implied_xml_id, raise_if_not_found=False)
        if not holder or not implied:
            _logger.warning(
                "Libro de Remuneraciones: no se pudo enlazar %s -> %s.",
                holder_xml_id, implied_xml_id)
            continue
        if implied in holder.implied_ids:
            continue
        holder.write({"implied_ids": [(4, implied.id)]})
        _logger.info(
            "Libro de Remuneraciones: %s implica ahora %s.",
            holder_xml_id, implied_xml_id)


def activate_seed_profiles(env):
    """Valida y activa los perfiles semilla contra ESTA base.

    Es idempotente y sólo escribe cuando el resultado cambia, porque también se
    ejecuta en cada arranque del registro desde `_register_hook`.
    """
    for xml_id in SEED_PROFILE_XML_IDS:
        profile = env.ref(xml_id, raise_if_not_found=False)
        if not profile:
            continue
        errors = profile.validation_errors()
        if errors:
            message = "\n".join("• %s" % error for error in errors)
            if profile.state != "draft" or profile.validation_message != message:
                profile.write({"state": "draft", "validation_message": message})
                _logger.info(
                    "Libro de Remuneraciones: el perfil %s queda en borrador "
                    "porque no supera la validación en esta base.",
                    profile.code)
            continue
        if profile.state != "active":
            profile.write({
                "state": "active",
                "validation_message": "Validación superada en esta base.",
            })
            _logger.info(
                "Libro de Remuneraciones: perfil %s activo.", profile.code)


def post_init_hook(env):
    ensure_group_implications(env)
    activate_seed_profiles(env)
