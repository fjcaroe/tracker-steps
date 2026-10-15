{
    'name': 'Steps - Documentos comerciales y Packing List',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['step_export_shipping_design', 'step_sale_export_report', 'step_packing_operations'],
    'data': ['views/documents.xml', 'report/documents.xml', 'report/packing.xml'],
    'external_dependencies': {'python': ['xlsxwriter']},
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
