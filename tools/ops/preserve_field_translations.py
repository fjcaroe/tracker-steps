"""Retain existing localized metadata when native reflection keeps its source text.

Only the short-lived canonical upgrade runner installs this adapter. New source
texts and explicitly supplied translations retain normal Odoo behavior.
"""

def capture(cr,model_names):
    cr.execute("""SELECT id,field_description,help FROM ir_model_fields
            WHERE model=ANY(%s) AND (coalesce(field_description-'en_US','{}'::jsonb)<>'{}'::jsonb
                OR coalesce(help-'en_US','{}'::jsonb)<>'{}'::jsonb)""",(list(model_names),))
    before=[dict(id=row[0],field_description=row[1],help=row[2]) for row in cr.fetchall()]
    return before

def restore(cr,before):
    from psycopg2.extras import Json
    if not before:
        return 0
    cr.execute("""WITH old AS (
        SELECT * FROM jsonb_to_recordset(%s::jsonb)
        AS x(id integer,field_description jsonb,help jsonb))
        UPDATE ir_model_fields f SET
            field_description=CASE WHEN f.field_description->>'en_US'=old.field_description->>'en_US'
                THEN old.field_description||f.field_description ELSE f.field_description END,
            help=CASE WHEN f.help->>'en_US'=old.help->>'en_US'
                THEN old.help||f.help ELSE f.help END
        FROM old WHERE f.id=old.id AND (
            (f.field_description->>'en_US'=old.field_description->>'en_US'
                AND old.field_description||f.field_description IS DISTINCT FROM f.field_description)
            OR (f.help->>'en_US'=old.help->>'en_US'
                AND old.help||f.help IS DISTINCT FROM f.help))""",(Json(before),))
    return cr.rowcount

def install():
    import logging
    from odoo.addons.base.models.ir_model import IrModelFields
    original=IrModelFields._reflect_fields
    if getattr(original,'_steps_preserve_field_translations',False):
        return
    logger=logging.getLogger(__name__)

    def reflect(records,model_names):
        names=list(model_names)
        before=capture(records.env.cr,names)
        result=original(records,names)
        if before:
            restored=restore(records.env.cr,before)
            if restored:
                logger.info('Preserved existing localized field metadata: %s',restored)
                records.invalidate_model(['field_description','help'])
        return result

    reflect._steps_preserve_field_translations=True
    IrModelFields._reflect_fields=reflect
