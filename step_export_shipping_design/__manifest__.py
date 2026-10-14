{
    'name': 'Steps - Instructivo y folio comercial de embarque',
    'version': '18.0.1.0.0', 'license': 'LGPL-3',
    'depends': ['step_export_client_revision'],
    'data': ['security/access.csv', 'security/rules.xml', 'views/shipping.xml', 'report/instruction.xml'],
    'pre_init_hook': 'pre_init_hook', 'post_init_hook': 'post_init_hook',
    'installable': True,
}
