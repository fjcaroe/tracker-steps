{
    'name': 'Cerro El Plomo - Lista de fundos',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_cerro_studio_adoption', 'step_agriculture_shared_farms'],
    'data': ['views/customizations.xml'],
    'pre_init_hook': 'adopt_views',
    'post_init_hook': 'preserve_alias',
    'installable': True,
}
