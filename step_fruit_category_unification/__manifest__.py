{
    'name': 'Steps - Categorías y clases de fruta compartidas',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_producer_fruit_reports'],
    'data': ['security/ir.model.access.csv', 'views/catalogs.xml'],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
