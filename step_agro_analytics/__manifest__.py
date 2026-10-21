{
    'name': 'Steps - Informes operacionales agrícolas',
    'version': '18.0.1.0.2', 'license': 'LGPL-3',
    'depends': ['step_export_dashboard', 'step_packing_operations',
                'step_inventory_packing', 'step_export_shipping_design'],
    'data': ['security/ir.model.access.csv', 'security/rules.xml',
             'views/standard.xml', 'views/shipments.xml'],
    'assets': {'web.assets_backend': [
        'step_agro_analytics/static/src/comparison.js',
        'step_agro_analytics/static/src/comparison.xml',
        'step_agro_analytics/static/src/comparison.scss',
    ]},
    'installable': True,
}
