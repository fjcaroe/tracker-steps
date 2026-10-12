from . import models


def post_init_hook(env):
    lines = env['step.export.estimate.line'].with_context(active_test=False).search([])
    for name in ('bin_qty', 'process_pallet_qty', 'export_box_qty', 'export_pallet_qty'):
        env.add_to_compute(lines._fields[name], lines)
    lines._recompute_recordset()
