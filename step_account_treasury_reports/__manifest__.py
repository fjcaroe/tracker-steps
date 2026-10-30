{
    'name': 'Steps - Tesorería: accesos Community',
    'summary': 'Conserva los cinco accesos originales con informes Community reales',
    'version': '18.0.2.0.0',
    'license': 'LGPL-3',
    'author': 'Steps Consulting',
    'depends': ['step_treasury_community_reports'],
    'pre_init_hook': 'pre_init_reports',
    'post_init_hook': 'post_init_reports',
    'installable': True,
}
