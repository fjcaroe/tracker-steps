{
    'name': 'Steps - Grupos de pagos Community',
    'summary': 'Gestión real de grupos en borrador; validación y conciliación pendientes',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'Steps Consulting',
    'depends': ['step_batch_payment_grouping', 'portal', 'rating'],
    'data': ['security/ir.model.access.csv', 'security/batch_rules.xml', 'views/batch_payment_views.xml'],
    'pre_init_hook': 'require_clean_provider',
    'installable': True,
}
