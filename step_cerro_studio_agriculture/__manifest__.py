{
    'name': 'Cerro El Plomo - Maestros agrícolas',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': [
        'step_cerro_studio_adoption',
        'step_hr',
        'step_cerro_studio_farms',
        'step_management_costs_agriculture',
    ],
    'pre_init_hook': 'adopt_views',
    'data': ['views/customizations.xml'],
    'installable': True,
}
