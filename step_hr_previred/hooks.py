"""Ganchos de instalación.

Los grupos de `hr_payroll` están marcados `noupdate="1"` en su propio módulo:
una implicación declarada desde otro addon se descarta en silencio y el
permiso *parecería* concedido sin estarlo. Por eso la implicación se aplica
aquí, de forma explícita e idempotente, en cada instalación y actualización.

Es el mismo mecanismo que usa `step_hr_remuneration_book`.
"""

import logging

_logger = logging.getLogger(__name__)

#: `nuestro grupo` implica `grupo ajeno`.
IMPLICATIONS = (
    ("step_hr_previred.group_previred_summary",
     "hr_payroll.group_hr_payroll_user"),
    ("step_hr_previred.group_previred_generate",
     "hr_payroll.group_hr_payroll_manager"),
    # Un administrador técnico debe poder abrir, configurar y auditar el
    # módulo desde el primer upgrade. Los demás usuarios reciben permisos de
    # forma explícita desde el perfil, sin ampliar el rol Nómina por defecto.
    ("base.group_system", "step_hr_previred.group_previred_generate"),
    ("base.group_system", "step_hr_previred.group_previred_technical"),
    ("base.group_system", "step_hr_previred.group_previred_audit"),
)


def ensure_group_implications(env):
    for own_xmlid, foreign_xmlid in IMPLICATIONS:
        own = env.ref(own_xmlid, raise_if_not_found=False)
        foreign = env.ref(foreign_xmlid, raise_if_not_found=False)
        if not own or not foreign:
            _logger.info(
                "Previred: no se pudo enlazar %s con %s; alguno no existe en "
                "esta base.", own_xmlid, foreign_xmlid)
            continue
        if foreign not in own.implied_ids:
            own.write({"implied_ids": [(4, foreign.id)]})
            _logger.info("Previred: %s ahora implica %s.",
                         own_xmlid, foreign_xmlid)


def post_init_hook(env):
    ensure_group_implications(env)
