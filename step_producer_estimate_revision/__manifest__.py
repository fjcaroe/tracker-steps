{
    'name': 'Steps - Envases y cálculos de estimaciones',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_producer_fruit_reports', 'step_producer_estimate_report'],
    'data': ['views/revision.xml'],
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
