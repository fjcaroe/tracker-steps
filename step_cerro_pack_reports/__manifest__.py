{
    'name': 'Cerro El Plomo - Consulta de tarjas y órdenes de trabajo',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_cerro_picking_list_history', 'step_inventory_fruit_tag', 'mail'],
    'pre_init_hook': 'adopt_originals',
    'installable': True,
}
