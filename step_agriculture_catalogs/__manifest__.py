{
    'name': 'Steps - Maestros agrícolas compartidos',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'Steps Consulting',
    'depends': ['step_hr'],
    'data': ['security/catalog_rules.xml', 'views/catalog_views.xml'],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
