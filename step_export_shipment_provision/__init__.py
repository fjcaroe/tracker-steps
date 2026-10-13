from . import models


def pre_init_hook(env):
    env.cr.execute('CREATE TEMP TABLE shipment_provision_original AS SELECT * FROM step_export_export')


def post_init_hook(env):
    env.flush_all()
    env.cr.execute("SELECT attname FROM pg_attribute WHERE attrelid='shipment_provision_original'::regclass AND attnum>0 AND NOT attisdropped")
    columns=[r[0] for r in env.cr.fetchall() if r[0]!='id']
    env.cr.execute('UPDATE step_export_export t SET '+','.join('"'+n+'"=o."'+n+'"' for n in columns)+' FROM shipment_provision_original o WHERE t.id=o.id')
    env.cr.execute('DROP TABLE shipment_provision_original')
    env.invalidate_all()
