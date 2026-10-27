def migrate(cr, version):
    cr.execute("UPDATE ir_model_data SET noupdate=true WHERE module='step_cosecha' AND model='ir.sequence' AND name IN ('seq_step_cosecha_propio','seq_step_cosecha_contra')")
    cr.execute("SELECT 1 FROM ir_model_data WHERE module='step_cosecha' AND model='ir.model' AND name IN ('model_hr_input_step_wizard','model_hr_entry_xls_wizard','model_success_message') LIMIT 1")
    if cr.fetchone():
        cr.execute("SELECT 1 FROM ir_module_module WHERE name='step_labor_payroll_wizards' AND state IN ('installed','to install','to upgrade')")
        if not cr.fetchone():
            raise RuntimeError('Instale el puente real step_labor_payroll_wizards en el mismo paquete; no retire los modelos compartidos de Nomina.')
    cr.execute("""UPDATE ir_model_data d SET noupdate=true WHERE d.module='step_cosecha' AND (
        (d.model='ir.model' AND d.res_id IN (SELECT id FROM ir_model WHERE model IN ('hr.input.step.wizard','hr.entry.xls.wizard','success.message'))) OR
        (d.model='ir.model.fields' AND d.res_id IN (SELECT id FROM ir_model_fields WHERE model IN ('hr.input.step.wizard','hr.entry.xls.wizard','success.message'))) OR
        (d.model='ir.model.fields.selection' AND d.res_id IN (SELECT s.id FROM ir_model_fields_selection s JOIN ir_model_fields f ON f.id=s.field_id WHERE f.model IN ('hr.input.step.wizard','hr.entry.xls.wizard','success.message'))))""")
