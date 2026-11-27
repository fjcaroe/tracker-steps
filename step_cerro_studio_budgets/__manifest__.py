{
    'name': 'Cerro El Plomo - Presupuestos y categorías',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'step_cerro_studio_adoption',
        'step_budget_design',
        'step_management_costs',
        'stock_account',
    ],
    'pre_init_hook': 'adopt_views',
    'data': ['views/customizations.xml'],
    'installable': True,
}
