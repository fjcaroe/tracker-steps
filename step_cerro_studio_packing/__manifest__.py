{
    'name': 'Cerro El Plomo - Packing y despachos',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'step_cerro_studio_adoption',
        'step_packing_operations',
        'step_packing_overweight',
        'step_packing_ticket_revision',
        'step_packing_reception_revision',
        'step_operations_ui',
        'step_packing_interplant',
    ],
    'pre_init_hook': 'adopt_views',
    'data': ['views/customizations.xml'],
    'installable': True,
}
