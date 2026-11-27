{
    'name': 'Cerro El Plomo - Seguimiento de cobros en contactos',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['account', 'step_cerro_export_contacts'],
    'pre_init_hook': 'adopt_history',
    'installable': True,
}
