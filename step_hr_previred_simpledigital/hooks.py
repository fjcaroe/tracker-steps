"""Redirección idempotente del menú Previred del motor SimpleDigital."""

import logging

_logger = logging.getLogger(__name__)

#: Menú que el motor ya publicaba y que debe apuntar al asistente nuevo.
MENU_XMLID = "l10n_cl_simpledigital_payroll.menu_hr_payroll_previred_txt"
#: Acción del asistente unificado de Steps.
ACTION_XMLID = "step_hr_previred.action_previred_export_wizard"
#: Perfil de este motor, para sincronizar lo que el adaptador declara.
PROFILE_XMLIDS = (
    "step_hr_previred_simpledigital.profile_simpledigital_v84",
    "step_hr_previred_simpledigital.profile_simpledigital_v98",
)


def redirect_previred_menu(env):
    """Apunta el menú del motor al asistente de Steps.

    Es idempotente: si ya apunta ahí, no escribe. No se hace con un registro
    de datos porque una actualización del addon del proveedor lo revertiría;
    el gancho corre en cada instalación y actualización de este puente.
    """
    menu = env.ref(MENU_XMLID, raise_if_not_found=False)
    action = env.ref(ACTION_XMLID, raise_if_not_found=False)
    if not menu or not action:
        _logger.info(
            "Previred SimpleDigital: no se pudo redirigir %s (menú=%s, acción=%s).",
            MENU_XMLID, bool(menu), bool(action))
        return
    target = "ir.actions.act_window,%d" % action.id
    if menu.action and str(menu.action) == target:
        return
    menu.write({"action": target, "name": "Previred TXT Remuneraciones"})
    _logger.info("Previred SimpleDigital: menú %s redirigido al asistente Steps.",
                 MENU_XMLID)


def sync_profile(env):
    for xmlid in PROFILE_XMLIDS:
        profile = env.ref(xmlid, raise_if_not_found=False)
        if profile:
            profile.sync_from_adapter()


def post_init_hook(env):
    redirect_previred_menu(env)
    sync_profile(env)
