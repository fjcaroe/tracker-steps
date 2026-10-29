{
    'name': 'Steps - Formatos bancarios Community',
    'summary': 'BancoEstado y Security sobre pagos y cuentas bancarias originales',
    'version': '18.0.1.2.1',
    'author': 'Steps Consulting',
    'license': 'LGPL-3',
    'depends': ['account'],
    'external_dependencies': {'python': ['xlwt', 'xlsxwriter']},
    'data': ['security/ir.model.access.csv', 'security/bank_export_rules.xml',
             'views/res_partner_bank_views.xml', 'wizard/bank_export_wizard_views.xml'],
    'pre_init_hook': 'adopt_legacy_fields',
    'post_init_hook': 'preserve_legacy_xmlids',
    'installable': True,
}
