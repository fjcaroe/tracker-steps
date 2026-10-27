"""Keep original packaging audit during initialization of new computed columns.

Fail before restoring audit if any original business column or record changed.
No masking of business changes and no alteration of user-entered quantities.
"""
from odoo.exceptions import UserError


def preserve_packaging_before(env):
    env.cr.execute('CREATE TEMP TABLE step_packaging_before AS SELECT * FROM product_packaging')


def restore_packaging_audit(env):
    env.flush_all()
    def columns(table):
        env.cr.execute('SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass '
                       'AND attnum>0 AND NOT attisdropped', (table,))
        return {row[0] for row in env.cr.fetchall()}
    added = sorted(columns('product_packaging') - columns('step_packaging_before'))
    env.cr.execute("SELECT 1 FROM product_packaging current FULL JOIN step_packaging_before old USING(id) "
                   "WHERE current.id IS NULL OR old.id IS NULL OR "
                   "(to_jsonb(current)-%s::text[]-ARRAY['write_uid','write_date']) IS DISTINCT FROM "
                   "(to_jsonb(old)-ARRAY['write_uid','write_date']) LIMIT 1", (added,))
    if env.cr.fetchone():
        raise UserError('La instalación modificó valores originales de embalajes; se cancela para conservarlos.')
    env.cr.execute('UPDATE product_packaging current SET write_uid=old.write_uid,write_date=old.write_date '
                   'FROM step_packaging_before old WHERE current.id=old.id')
    env.cr.execute('DROP TABLE step_packaging_before')
    env.invalidate_all()
