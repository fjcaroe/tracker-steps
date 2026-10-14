{
    'name': 'Steps - Provisión gastos de embarques',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['step_export', 'l10n_latam_invoice_document'],
    'data': ['security/ir.model.access.csv', 'security/rules.xml', 'views/provision.xml'],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
