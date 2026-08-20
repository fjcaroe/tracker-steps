{
    'name': 'Steps Tracker para Odoo',
    'summary': 'Tablero, operación y sincronización de Web Tracker',
    'version': '18.0.1.0.0',
    'category': 'Operations',
    'author': 'Steps Consulting',
    'license': 'LGPL-3',
    'depends': ['base', 'base_setup', 'web', 'mail', 'fleet', 'hr', 'account'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'data/step_tracker_cron.xml',
        'views/res_config_settings_views.xml',
        'views/step_tracker_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'step_tracker_odoo/static/src/js/tracker_dashboard.js',
            'step_tracker_odoo/static/src/xml/tracker_dashboard.xml',
            'step_tracker_odoo/static/src/scss/tracker_dashboard.scss',
        ],
    },
    'application': True,
    'installable': True,
}
