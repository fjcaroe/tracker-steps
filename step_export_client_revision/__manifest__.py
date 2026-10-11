{
    'name': 'Steps - Revisión comercial Exportaciones y Packing',
    'version': '18.0.1.0.0', 'license': 'LGPL-3',
    'depends': ['step_export', 'step_packing_operations', 'step_inventory_fruit_tag', 'step_sale_export_report', 'web_gantt'],
    'data': ['security/ir.model.access.csv', 'security/rules.xml', 'views/catalogs.xml',
             'views/forms.xml', 'views/program_report.xml'],
    'post_init_hook': 'post_init_hook', 'installable': True,
}
