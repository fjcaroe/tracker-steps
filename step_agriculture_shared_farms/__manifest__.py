{
    'name': 'Steps - Fundos compartidos y grupos de productores',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_producers'],
    'data': ['security/farm_rule.xml'],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
