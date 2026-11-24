{
    'name': 'Steps - Operación de cosecha contratista',
    'version': '18.0.1.1.0',
    'license': 'LGPL-3',
    'depends': ['step_cosecha_planning', 'step_packing'],
    'data': ['views/operations.xml', 'views/harvest_tariffs.xml', 'views/dashboard_settings.xml'],
    'assets': {'web.assets_backend': [
        'step_cosecha_operations/static/src/scss/tariffs.scss',
        'step_cosecha_operations/static/src/js/dashboard.js',
        'step_cosecha_operations/static/src/xml/dashboard.xml',
        'step_cosecha_operations/static/src/scss/dashboard.scss',
    ]},
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
