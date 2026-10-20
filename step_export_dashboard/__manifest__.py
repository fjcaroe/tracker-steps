{
    'name': 'Steps - Comparativo de exportaciones',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_export'],
    'assets': {'web.assets_backend': [
        'step_export_dashboard/static/src/dashboard.js',
        'step_export_dashboard/static/src/dashboard.xml',
        'step_export_dashboard/static/src/dashboard.scss',
    ]},
    'installable': True,
}
