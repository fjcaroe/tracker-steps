{
    'name': 'Steps - Nóminas Banco Security',
    'version': '18.0.1.0.0', 'license': 'LGPL-3',
    'depends': ['step_account_treasury_batch'],
    'external_dependencies': {'python': ['xlwt']},
    'data': ['views/bank_export.xml'], 'installable': True,
}
