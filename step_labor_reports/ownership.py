CORE = 'step_labor_reports'
LEGACY = ('step_hr',)
MODELS = ('report.step.hrs.wizard', 'report.by.process.wizard')
RECORDS = {'access_report_by_process_wizard': 'ir.model.access',
 'access_report_step_hrs_wizard': 'ir.model.access',
 'model_report_by_process_wizard': 'ir.model',
 'model_report_step_hrs_wizard': 'ir.model',
 'report_step_by_process_action': 'ir.actions.act_window',
 'report_step_by_process_form': 'ir.ui.view',
 'report_step_hrs_wizard_action': 'ir.actions.act_window',
 'report_step_hrs_wizard_form': 'ir.ui.view'}
RELATIONS = ('employee_wizard_rel', 'employee_process_rel')
