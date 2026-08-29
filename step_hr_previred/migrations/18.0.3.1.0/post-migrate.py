"""Da acceso inicial a administradores técnicos, sin ampliar Nómina."""


def migrate(cr, version):
    cr.execute("""
        INSERT INTO res_groups_implied_rel (gid, hid)
        SELECT system_group.res_id, target.res_id
          FROM ir_model_data system_group
          JOIN ir_model_data target
            ON target.module = 'step_hr_previred'
           AND target.name IN (
               'group_previred_generate',
               'group_previred_technical',
               'group_previred_audit')
         WHERE system_group.module = 'base'
           AND system_group.name = 'group_system'
           AND NOT EXISTS (
               SELECT 1 FROM res_groups_implied_rel rel
                WHERE rel.gid = system_group.res_id
                  AND rel.hid = target.res_id)
    """)

