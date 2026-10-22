{
    'name': 'Steps - Documentos agrícolas y centros de costos',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_cosecha_operations', 'step_machinery', 'step_packing',
                'step_management_costs_agriculture'],
    'data': ['security/ir.model.access.csv', 'views/documents.xml'],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
