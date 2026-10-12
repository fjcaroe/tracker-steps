from . import models


def pre_init_hook(env):
    # Registry initialization can fill nullable booleans and recomputation
    # writes audit columns. Preserve these unrelated original values exactly.
    # This migration scratch table exists only in the installation connection.
    env.cr.execute('CREATE TEMP TABLE estimate_revision_original_audit AS '
                   'SELECT id,write_uid,write_date,step_delivery_closed FROM step_export_estimate_line')


def post_init_hook(env):
    lines = env['step.export.estimate.line'].with_context(active_test=False).search([])
    for name in ('bin_qty', 'process_pallet_qty', 'export_box_qty', 'export_pallet_qty'):
        env.add_to_compute(lines._fields[name], lines)
    lines._recompute_recordset()
    env.flush_all()
    env.cr.execute('UPDATE step_export_estimate_line l SET write_uid=a.write_uid, '
                   'write_date=a.write_date,step_delivery_closed=a.step_delivery_closed '
                   'FROM estimate_revision_original_audit a WHERE l.id=a.id')
    env.cr.execute('DROP TABLE estimate_revision_original_audit')
    lines.invalidate_recordset(['write_uid','write_date','step_delivery_closed'])
