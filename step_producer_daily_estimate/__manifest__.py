{
    'name': 'Steps - Estimación diaria y mercados',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_producer_estimate_revision', 'hr'],
    'data': ['security/access.csv', 'security/rules.xml', 'views/daily.xml'],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
