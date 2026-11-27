{
    'name': 'Cerro El Plomo · Directorio de contactos de exportación',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_agriculture_core', 'stock', 'step_cerro_studio_adoption'],
    'data': ['views/customizations.xml'],
    'pre_init_hook': 'adopt_directory',
    'post_init_hook': 'verify_directory',
    'installable': True,
}
