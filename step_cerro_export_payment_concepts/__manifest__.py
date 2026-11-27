{
    'name': 'Cerro El Plomo - Conceptos de pago de exportación',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['product', 'step_cerro_studio_adoption'],
    'data': ['views/customizations.xml'],
    'pre_init_hook': 'adopt_concepts',
    'post_init_hook': 'verify_concepts',
    'installable': True,
}
