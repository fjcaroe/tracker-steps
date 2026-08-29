"""Materializa grupos implicados para administradores ya existentes."""


def migrate(cr, version):
    # Odoo materializa los grupos implicados en res_groups_users_rel. La
    # relación entre grupos ya existe; aquí se actualizan los usuarios que
    # eran administradores antes de instalar este módulo.
    cr.execute("""
        INSERT INTO res_groups_users_rel (gid, uid)
        SELECT target.res_id, current_users.uid
          FROM ir_model_data system_group
          JOIN res_groups_users_rel current_users
            ON current_users.gid = system_group.res_id
          JOIN ir_model_data target
            ON target.module = 'step_hr_previred'
           AND target.name IN (
               'group_previred_summary',
               'group_previred_generate',
               'group_previred_technical',
               'group_previred_audit')
         WHERE system_group.module = 'base'
           AND system_group.name = 'group_system'
           AND NOT EXISTS (
               SELECT 1 FROM res_groups_users_rel present
                WHERE present.gid = target.res_id
                  AND present.uid = current_users.uid)
    """)
