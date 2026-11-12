def post_init_hook(env):
    mapping = {'Despacho a cliente': 'customer', 'Retira cliente': 'customer',
               'Despacho a productor': 'producer', 'Traslado Interplanta': 'interplant'}
    for name, kind in mapping.items():
        env['step.freight.dispatch.type'].search([('name', '=', name),
            ('step_recipient_kind', '=', False)]).write({'step_recipient_kind': kind})
