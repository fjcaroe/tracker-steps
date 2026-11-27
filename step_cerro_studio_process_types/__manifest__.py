{
    'name': 'Cerro El Plomo - Tipos de proceso de packing',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['step_cerro_studio_adoption', 'step_packing_process_category'],
    'data': ['views/customizations.xml'],
    'pre_init_hook': 'adopt_views',
    'post_init_hook': 'preserve_alias',
    'installable': True,
}
