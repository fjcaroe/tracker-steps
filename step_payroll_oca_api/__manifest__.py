{'name': 'step_payroll_oca_api',
 'version': '18.0.1.6.0',
 'license': 'LGPL-3',
 'depends': ['payroll_account', 'step_payroll_contracts', 'hr_work_entry_contract', 'hr_work_entry_holidays'],
 'data': ['security/ir.model.access.csv', 'views/payroll_structure.xml'],
 'pre_init_hook': 'pre_init_hook',
 'installable': True,
 'application': False}
