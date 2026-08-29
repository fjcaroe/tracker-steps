"""Ajustes idempotentes para la vigencia v84/v98 y permisos corporativos."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # El registro v84 está en noupdate porque forma parte del histórico; se
    # cierra explícitamente para que no compita con v98 desde agosto de 2026.
    cr.execute("""
        UPDATE step_previred_profile
           SET effective_to = '2026-07'
         WHERE spec_version = '84'
           AND (effective_to IS NULL OR effective_to = '')
    """)
    _logger.info("Previred: cerrados %s perfiles v84 en 2026-07.", cr.rowcount)

    # `post_init_hook` no corre en todas las rutas de upgrade; la migración
    # garantiza que generar Previred implique Administrador de Nómina.
    cr.execute("""
        INSERT INTO res_groups_implied_rel (gid, hid)
        SELECT own.res_id, manager.res_id
          FROM ir_model_data own
          JOIN ir_model_data manager ON manager.module = 'hr_payroll'
                                    AND manager.name = 'group_hr_payroll_manager'
         WHERE own.module = 'step_hr_previred'
           AND own.name = 'group_previred_generate'
           AND NOT EXISTS (
               SELECT 1 FROM res_groups_implied_rel rel
                WHERE rel.gid = own.res_id AND rel.hid = manager.res_id)
    """)

