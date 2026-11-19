{
    'name': 'Steps - Presupuestos por temporada y unidad de cálculo',
    'version': '18.0.1.3.1', 'license': 'LGPL-3',
    'depends': ['step_management_costs_agriculture', 'step_management_costs_machinery', 'step_agriculture_records'],
    'data': ['security/ir.model.access.csv', 'security/rules.xml', 'data/masters.xml', 'views/budget.xml',
             'security/actual_costs.xml', 'views/actual_costs.xml'],
    'assets': {'web.assets_backend': [
        ('replace', 'step_management_costs/static/src/js/management_dashboard.js',
         'step_budget_design/static/src/js/dashboard.js'),
        ('replace', 'step_management_costs/static/src/xml/management_dashboard.xml',
         'step_budget_design/static/src/xml/dashboard.xml'),
        'step_budget_design/static/src/scss/dashboard.scss',
    ]},
    'pre_init_hook': 'pre_init_hook', 'post_init_hook': 'post_init_hook',
    'installable': True,
}
