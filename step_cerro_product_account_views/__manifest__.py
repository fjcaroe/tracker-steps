{
    'name': 'Cerro El Plomo - Cuentas y categorías de producto',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['account', 'hr_expense'],
    'pre_init_hook': 'adopt_views',
    'data': ['views/product_views.xml'],
    'installable': True,
}
