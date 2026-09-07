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

SALARY_RULE_CONDITIONS = {
    "l10n_cl_simpledigital_payroll.hr_AFP_Em": """result = (
    contract.pension_option == 'afp'
    and contract.afp_option not in ['00 - 100']
    and not contract.is_retired_elderly
    and not payslip._step_previred_active_over_65()
)""",
    "l10n_cl_simpledigital_payroll.hr_rule_sis": """result = (
    contract.pension_option == 'afp'
    and contract.afp_option not in ['00 - 100']
    and not contract.is_retired_elderly
    and not payslip._step_previred_active_over_65()
)""",
    "l10n_cl_simpledigital_payroll.hr_rule_Expec_vida": """result = (
    not contract.is_retired_elderly
    and not payslip._step_previred_active_over_65()
)""",
    "l10n_cl_simpledigital_payroll.hr_rule_rentabilidad_protegida": """result = (
    contract.pension_option == 'afp'
    and contract.afp_option not in ['00 - 100']
    and not contract.is_retired_elderly
    and not payslip._step_previred_active_over_65()
)""",
}


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


def apply_salary_rule_overrides(env):
    """Aplica condiciones aunque los datos del proveedor sean noupdate."""
    for xmlid, condition in SALARY_RULE_CONDITIONS.items():
        rule = env.ref(xmlid, raise_if_not_found=False)
        if not rule:
            _logger.warning(
                "Previred SimpleDigital: no existe la regla %s.", xmlid
            )
            continue
        if rule.condition_python != condition:
            rule.write({"condition_python": condition})
            _logger.info(
                "Previred SimpleDigital: regla %s actualizada para tipo 3.",
                xmlid,
            )


def post_init_hook(env):
    redirect_previred_menu(env)
    sync_profile(env)
    apply_salary_rule_overrides(env)
