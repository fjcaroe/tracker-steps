"""Rename existing freight masters/documents in place, including their references."""
import importlib.util
from pathlib import Path


def migrate(cr, version):
    spec = importlib.util.spec_from_file_location('freight_native_schema', Path(__file__).parents[2] / 'native_schema.py')
    schema = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(schema)
    # Stored related model names also occur in automation, document and mail
    # metadata. Updating only ir.model leaves their references stale.
    cr.execute("""SELECT table_name,column_name FROM information_schema.columns
        WHERE table_schema='public' AND data_type IN ('character varying','text')
          AND column_name IN ('model','model_name','res_model','res_model_name')""")
    model_references = cr.fetchall()
    for old, new in schema.MODELS.items():
        table = new.replace('.', '_')
        cr.execute('SELECT to_regclass(%s),to_regclass(%s)', (old, table))
        source, target = cr.fetchone()
        if source and target:
            raise RuntimeError('Parallel freight tables exist; refuse ambiguous migration: ' + old)
        if source:
            cr.execute(f'ALTER TABLE "{old}" RENAME TO "{table}"')
            cr.execute('SELECT to_regclass(%s)', (old + '_id_seq',))
            if cr.fetchone()[0]:
                cr.execute(f'ALTER SEQUENCE "{old}_id_seq" RENAME TO "{table}_id_seq"')
        cr.execute("SELECT id FROM ir_model WHERE model=%s", (old,))
        row = cr.fetchone()
        if not row:
            continue
        model_id = row[0]
        cr.execute('SELECT to_regclass(%s)', (table,))
        if cr.fetchone()[0]:
            cr.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (table,))
            columns = {row[0] for row in cr.fetchall()}
            for old_field, new_field in schema.FIELDS.items():
                if old_field not in columns:
                    continue
                if new_field in columns:
                    raise RuntimeError('Parallel freight fields exist: ' + table + '/' + new_field)
                cr.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{old_field}" TO "{new_field}"')
                columns.remove(old_field)
                columns.add(new_field)
        # Convert all metadata for this model before loading Python. Preserve
        # the model/field IDs, foreign keys, chatter, attachments and ACLs.
        cr.execute("SELECT id,name,related FROM ir_model_fields WHERE model=%s", (old,))
        for field_id, old_field, related in cr.fetchall():
            new_field = schema.FIELDS.get(old_field, old_field)
            if new_field.startswith('x_'):
                raise RuntimeError('Unmapped freight field: ' + old + '/' + old_field)
            cr.execute("UPDATE ir_model_fields SET model=%s,name=%s,state='base',related=%s WHERE id=%s",
                       (new, new_field, schema.replace_tokens(related, schema.FIELDS) if related else related, field_id))
            cr.execute("UPDATE ir_model_data SET name=%s WHERE module='step_operations_ui' AND model='ir.model.fields' AND res_id=%s",
                       ('field_' + table + '__' + new_field, field_id))
        cr.execute("UPDATE ir_model SET model=%s,state='base' WHERE id=%s", (new, model_id))
        cr.execute("UPDATE ir_model_fields SET relation=%s WHERE relation=%s", (new, old))
        cr.execute("UPDATE ir_model_data SET name=%s WHERE module='step_operations_ui' AND model='ir.model' AND res_id=%s",
                   ('model_' + table, model_id))
        # Retire foreign Studio views; own XML is reloaded with native fields.
        cr.execute("""UPDATE ir_ui_view v SET active=false WHERE v.model=%s AND
            EXISTS (SELECT 1 FROM ir_model_data d WHERE d.model='ir.ui.view' AND d.res_id=v.id
                    AND d.module='studio_customization')""", (old,))
        for metadata, column in (('ir_ui_view','model'),('ir_act_window','res_model'),
                                 ('ir_act_report_xml','model'),('mail_message','model'),
                                 ('mail_followers','res_model'),('mail_activity','res_model'),
                                 ('ir_attachment','res_model'),('ir_model_data','model')):
            cr.execute(f'UPDATE "{metadata}" SET "{column}"=%s WHERE "{column}"=%s', (new, old))
        for metadata, column in model_references:
            cr.execute(f'UPDATE "{metadata}" SET "{column}"=%s WHERE "{column}"=%s', (new, old))
        cr.execute('UPDATE ir_sequence SET code=%s WHERE code=%s', (new, old))
        replacements = {**schema.FIELDS, **{'default_' + key: 'default_' + value for key, value in schema.FIELDS.items()}}
        cr.execute('SELECT id,domain,context FROM ir_act_window WHERE res_model=%s', (new,))
        for action_id, domain, context in cr.fetchall():
            cr.execute('UPDATE ir_act_window SET domain=%s,context=%s WHERE id=%s',
                       (schema.replace_tokens(domain, replacements) if domain else domain,
                        schema.replace_tokens(context, replacements) if context else context, action_id))
        cr.execute('SELECT id,domain,context FROM ir_filters WHERE model_id=%s', (old,))
        for filter_id, domain, context in cr.fetchall():
            cr.execute('UPDATE ir_filters SET model_id=%s,domain=%s,context=%s WHERE id=%s',
                       (new, schema.replace_tokens(domain, replacements) if domain else domain,
                        schema.replace_tokens(context, replacements) if context else context, filter_id))
        cr.execute("""UPDATE ir_act_report_xml SET binding_model_id=NULL WHERE model=%s AND
            EXISTS (SELECT 1 FROM ir_model_data d WHERE d.model='ir.actions.report'
                    AND d.res_id=ir_act_report_xml.id AND d.module='studio_customization')""", (new,))
        cr.execute('SELECT id,code FROM ir_act_server WHERE model_id=%s', (model_id,))
        for action_id, code in cr.fetchall():
            if code:
                cr.execute('UPDATE ir_act_server SET code=%s WHERE id=%s',
                           (schema.replace_tokens(schema.replace_tokens(code, schema.MODELS), schema.FIELDS), action_id))
    # No manual field/model aliases survive on the operational freight models.
