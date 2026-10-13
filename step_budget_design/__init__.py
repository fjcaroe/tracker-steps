from . import models

TABLES = ('step_management_budget_template','step_management_budget_template_line','step_management_budget_group',
          'step_management_operational_budget','step_management_budget_center','step_management_budget_line','step_management_budget_month')


def pre_init_hook(env):
    for table in TABLES:
        env.cr.execute('CREATE TEMP TABLE budget_original_'+table+' AS SELECT * FROM '+table)


def post_init_hook(env):
    env.flush_all()
    for table in TABLES:
        scratch='budget_original_'+table
        env.cr.execute('SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped',(scratch,))
        columns=[r[0] for r in env.cr.fetchall() if r[0]!='id']
        env.cr.execute('UPDATE '+table+' t SET '+','.join('"'+n+'"=o."'+n+'"' for n in columns)+' FROM '+scratch+' o WHERE t.id=o.id')
        env.cr.execute('DROP TABLE '+scratch)
    env.invalidate_all()
