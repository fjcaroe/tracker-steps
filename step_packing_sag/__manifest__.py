{
    'name': 'Steps Packing - Prototipo de inspección SAG',
    'version': '18.0.2.0.0',
    'license': 'LGPL-3',
    'depends': ['step_packing_dispatch', 'step_producer_fruit_reports'],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': ['security/ir.model.access.csv', 'data/services.xml', 'views/inspection.xml', 'views/masters.xml', 'report/dispatch_annex.xml'],
    'installable': True,
}
