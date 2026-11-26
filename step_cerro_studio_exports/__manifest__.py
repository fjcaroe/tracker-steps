{
    'name': 'Cerro El Plomo - Instrucciones y costos de exportación',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'step_cerro_studio_adoption',
        'step_export_client_revision',
        'step_export_receiver_profile',
        'step_export',
    ],
    'pre_init_hook': 'adopt_views',
    'data': ['views/customizations.xml'],
    'installable': True,
}
