{
    'name': 'Steps - Tesorería: informes Enterprise',
    'summary': 'Puente opcional para los cinco accesos contables Enterprise',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'Steps Consulting',
    'depends': ['step_account_treasury', 'account_reports', 'step_accounting_multicurrency'],
    'pre_init_hook': 'pre_init_reports',
    'post_init_hook': 'post_init_reports',
    'installable': True,
}
