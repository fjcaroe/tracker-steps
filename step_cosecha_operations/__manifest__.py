{
    'name': 'Steps - Operación de cosecha contratista',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_cosecha_planning', 'step_packing'],
    'data': ['views/operations.xml'],
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
