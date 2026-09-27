"""Fase 5 — migración idempotente a 18.0.11.0.0.

Sólo agrega el motor de programas fitosanitarios / de fertilización
(`step_management_crop_program*`, tablas creadas por el ORM). No hay datos que
backfillear; se deja evidencia del upgrade. Reejecutable sin efecto.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT count(*) FROM information_schema.tables
         WHERE table_name = 'step_management_crop_program'
    """)
    if not cr.fetchone()[0]:
        return
    cr.execute("SELECT count(*) FROM step_management_crop_program")
    programs = cr.fetchone()[0]
    cr.execute("SELECT count(*) FROM step_management_crop_program_application")
    applications = cr.fetchone()[0]
    _logger.info(
        "18.0.11.0.0: %s programa(s) y %s aplicación(es) preservadas.",
        programs, applications,
    )
