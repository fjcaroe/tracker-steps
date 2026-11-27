{
    'name': 'Cerro El Plomo - Productos y estimaciones',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': [
        'step_cerro_studio_adoption',
        'step_product_bpa',
        'step_producers',
        'step_agriculture_core',
    ],
    'pre_init_hook': 'adopt_views',
    'data': ['views/customizations.xml'],
    'installable': True,
}
