{'name': 'step_labor_reports',
 'version': '18.0.1.0.0',
 'license': 'AGPL-3',
 'depends': ['step_labor_operations_core'],
 'data': ['security/ir.model.access.csv', 'views/reports.xml'],
 'pre_init_hook': 'pre_init_hook',
 'post_init_hook': 'post_init_hook',
 'installable': True}
