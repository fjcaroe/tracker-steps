{
    'name': 'Cerro El Plomo - Especies y cargas de fruta',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'step_cerro_studio_adoption',
        'step_producer_fruit_reports',
        'step_agriculture_catalogs',
        'step_hr',
    ],
    'pre_init_hook': 'adopt_views',
    'data': ['views/customizations.xml'],
    'installable': True,
}
