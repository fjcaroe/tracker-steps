def post_init_hook(env):
    mapping = {'Despacho a cliente': 'customer', 'Retira cliente': 'customer',
               'Despacho a productor': 'producer', 'Traslado Interplanta': 'interplant'}
    for name, kind in mapping.items():
        records = env['step.freight.dispatch.type'].search([('name', '=', name),
            ('step_recipient_kind', '=', False)])
        if records:
            # Initialize only the newly introduced classification, preserving
            # historical business values and their audit timestamps.
            env.cr.execute('UPDATE step_freight_dispatch_type SET step_recipient_kind=%s WHERE id IN %s',
                [kind, tuple(records.ids)])
            records.invalidate_recordset(['step_recipient_kind'])
