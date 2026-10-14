from . import models


TABLES = ('step_export_export', 'step_export_shipment_line', 'sale_order', 'account_move', 'res_company')


def pre_init_hook(env):
    for table in TABLES:
        env.cr.execute('CREATE TEMP TABLE shipping_original_' + table + ' AS SELECT * FROM ' + table)


def post_init_hook(env):
    env.flush_all()
    for table in TABLES:
        temporary = 'shipping_original_' + table
        env.cr.execute("SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped", [temporary])
        columns = [r[0] for r in env.cr.fetchall() if r[0] != 'id']
        env.cr.execute('UPDATE ' + table + ' t SET ' + ','.join('"'+n+'"=o."'+n+'"' for n in columns) + ' FROM ' + temporary + ' o WHERE t.id=o.id')
        env.cr.execute('DROP TABLE ' + temporary)
    env.invalidate_all()
