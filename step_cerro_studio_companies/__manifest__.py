{
    'name': 'Cerro El Plomo - Directorio de empresas',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'step_cerro_studio_adoption',
        'l10n_cl_communes',
    ],
    'pre_init_hook': 'adopt_views',
    'data': ['views/customizations.xml'],
    'installable': True,
}
