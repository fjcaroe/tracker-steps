"""Verify that the archived workbook interface changes only the five original availability flags."""
from compare_sys_full_restore import snapshot
from check_steps_crm_preservation import compare
from prepare_steps_quote_forms import prepare, VIEWS


def menus_and_views(cursor):
    result = {}
    for table in ('ir_ui_view', 'ir_ui_menu'):
        cursor.execute(f"""SELECT id,active,encode(sha256(convert_to((to_jsonb(r)-'active')::text,'UTF8')),'hex')
                           FROM {table} r ORDER BY id""")
        result[table] = {key: (flag, body) for key,flag,body in cursor.fetchall()}
    return result


def check(connection, database):
    required = ('crm_lead','sale_order','ir_attachment')
    before = snapshot(database, required_nonempty=required)
    with connection.cursor() as cursor:
        source = menus_and_views(cursor)
        applied = prepare(cursor)
        if applied['database'] != database:
            raise ValueError('Incorrect private database.')
        changes = {'ir_ui_view': {row[0] for row in VIEWS.values()}, 'ir_ui_menu':{329}}
        after = menus_and_views(cursor)
        for table, items in source.items():
            expected = {key:(False if key in changes[table] else flag,body) for key,(flag,body) in items.items()}
            if after[table] != expected:
                raise ValueError('Another routing or view attribute changed.')
        if prepare(cursor) != applied or menus_and_views(cursor) != after:
            raise ValueError('The quotation form migration cannot be rerun safely.')
    connection.commit()
    final = snapshot(database, required_nonempty=required)
    differences = {name: sorted(key for key in rows.keys() | final[name].keys() if rows.get(key) != final[name].get(key))
                   for name,rows in before.items()}
    changed = any(source['ir_ui_view'][key][0] for key in changes['ir_ui_view'])
    expected_tables = ['ir_ui_menu','ir_ui_view'] if changed else []
    if differences['public_tables'] != expected_tables or any(
            values for key,values in differences.items() if key != 'public_tables'):
        raise ValueError('Unexpected change to tables, schema or counters.')
    return {**applied,'differences':differences,'rows':sum(value[0] for value in before['public_tables'].values()),
            'tables':len(before['public_tables']),'original_counters':len(before['sequence_values'])}


def check_after_trial(connection, database, plan):
    if database != 'COMMUNITY_STEPS_CRM_QUOTE_20261127U42A':
        raise ValueError('Expected the qualified Steps quotation copy.')
    with connection.cursor() as cursor:
        before = menus_and_views(cursor)
        prepare(cursor)
        if menus_and_views(cursor) != before:
            raise ValueError('The archived workbook interface has changed since the trial.')
    connection.rollback()
    reference = 'MANAGEMENT_QA_STEPS_CRM_20261126U42E'
    report = compare(reference, database, plan)
    differences = report['differences']
    if (report['unexpected_modules'] or differences['public_tables'] != ['ir_module_module','ir_ui_menu','ir_ui_view']
            or any(value for key,value in differences.items() if key not in ('public_tables','sequence_values'))):
        raise ValueError('Historical business rows or the original schema changed during the quotation trial.')
    return report
