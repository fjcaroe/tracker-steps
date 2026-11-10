{
    'name': 'Steps - Períodos del panel de Actividades',
    'version': '18.0.1.0.0',
    'license': 'AGPL-3',
    'depends': ['step_hr'],
    'assets': {
        'web.assets_backend': [
            'step_activities_dashboard_periods/static/src/dashboard.js',
            'step_activities_dashboard_periods/static/src/dashboard.xml',
        ],
    },
    'installable': True,
}
