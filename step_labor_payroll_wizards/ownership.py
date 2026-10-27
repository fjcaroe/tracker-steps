CORE = 'step_labor_payroll_wizards'
LEGACY = ('step_hr', 'step_cosecha')
MODELS = ('hr.input.step.wizard', 'hr.entry.xls.wizard', 'success.message')
RECORDS = {'access_hr_entry_xls_wizard': 'ir.model.access',
 'access_success_message': 'ir.model.access',
 'hr_entry_xls_wizard_action': 'ir.actions.act_window',
 'hr_entry_xls_wizard_form': 'ir.ui.view',
 'menu_hr_entry_xls_wizard': 'ir.ui.menu',
 'menu_step_payslip_wizard': 'ir.ui.menu',
 'model_hr_entry_xls_wizard': 'ir.model',
 'model_hr_input_step_wizard': 'ir.model',
 'model_success_message': 'ir.model',
 'step_payslip_wizard_action': 'ir.actions.act_window',
 'step_payslip_wizard_form': 'ir.ui.view'}
RELATIONS = ('step_hr_payslip_rel',)
