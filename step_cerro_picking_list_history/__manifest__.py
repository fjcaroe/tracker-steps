{
    'name': 'Cerro El Plomo - Consulta de traslados y recepciones',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_cerro_studio_transfers', 'step_packing'],
    'pre_init_hook': 'adopt_history',
    'post_init_hook': 'verify_history',
    'installable': True,
}
