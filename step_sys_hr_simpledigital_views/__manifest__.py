{
    'name': 'SyS – Empleados y cotización en Simple Digital',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'depends': ['step_sys_hr_fields', 'l10n_cl_simpledigital_payroll'],
    'pre_init_hook': 'adopt_views',
    'data': ['views/hr_views.xml'],
    'installable': True,
}
