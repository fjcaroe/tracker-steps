{
    'name': 'Cerro El Plomo - Traslados de fruta',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'step_cerro_studio_adoption',
        'step_packing',
    ],
    'pre_init_hook': 'adopt_views',
    'data': ['views/customizations.xml'],
    'installable': True,
}
