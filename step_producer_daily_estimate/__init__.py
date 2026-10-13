from . import models


def pre_init_hook(env):
    # Only transaction-local migration scratch; preserve existing business rows,
    # including nullable legacy booleans and audit columns touched by Odoo init.
    for table in ('step_export_estimate', 'step_export_estimate_line', 'step_export_estimate_week'):
        env.cr.execute('CREATE TEMP TABLE daily_original_' + table + ' AS SELECT * FROM ' + table)


def post_init_hook(env):
    env.flush_all()
    for table in ('step_export_estimate', 'step_export_estimate_line', 'step_export_estimate_week'):
        scratch = 'daily_original_' + table
        env.cr.execute('SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped', (scratch,))
        columns = [r[0] for r in env.cr.fetchall() if r[0] != 'id']
        env.cr.execute('UPDATE ' + table + ' t SET ' + ','.join('"'+n+'"=o."'+n+'"' for n in columns) + ' FROM ' + scratch + ' o WHERE t.id=o.id')
        env.cr.execute('DROP TABLE ' + scratch)
    env.invalidate_all()
