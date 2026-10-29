{
    'name': 'Steps - Contabilidad multimoneda Community',
    'summary': 'Moneda operacional, asientos y pagos sin motor Enterprise de informes',
    'version': '18.0.1.1.1',
    'author': 'Steps Consulting',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': ['views/account_move_views.xml', 'views/account_payment_views.xml',
             'views/res_config_settings_views.xml'],
    'pre_init_hook': 'adopt_legacy_records',
    'post_init_hook': 'preserve_legacy_xmlids',
    'installable': True,
}
