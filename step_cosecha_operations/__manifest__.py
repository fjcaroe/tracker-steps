{
    'name': 'Steps - Operación de cosecha contratista',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['step_cosecha_planning', 'step_packing'],
    'data': ['views/operations.xml', 'views/harvest_tariffs.xml'],
    'assets': {'web.assets_backend': ['step_cosecha_operations/static/src/scss/tariffs.scss']},
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
