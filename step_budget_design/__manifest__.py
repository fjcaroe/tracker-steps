{
    'name': 'Steps - Presupuestos por temporada y unidad de cálculo',
    'version': '18.0.1.1.0', 'license': 'LGPL-3',
    'depends': ['step_management_costs_agriculture', 'step_management_costs_machinery', 'step_agriculture_records'],
    'data': ['security/ir.model.access.csv', 'security/rules.xml', 'data/masters.xml', 'views/budget.xml'],
    'pre_init_hook': 'pre_init_hook', 'post_init_hook': 'post_init_hook',
    'installable': True,
}
