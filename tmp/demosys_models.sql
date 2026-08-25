SELECT model, name
FROM ir_model
WHERE model IN ('hr.causal.termino', 'step.fundo', 'hr.contract', 'hr.payslip');

SELECT d.module || '.' || d.name, m.name
FROM ir_model_data d
JOIN ir_ui_menu m ON d.model = 'ir.ui.menu' AND d.res_id = m.id
WHERE d.module IN ('l10n_cl_hr', 'l10n_cl_simpledigital_payroll', 'hr_payroll')
  AND (m.name::text ILIKE '%nómina%' OR m.name::text ILIKE '%payroll%' OR d.name ILIKE '%menu%base%')
ORDER BY 1;

SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'hr_contract'
  AND column_name IN ('afp_id','isapre_id','causal_id','tipo_de_jornada','department_id','job_id','resource_calendar_id','wage')
ORDER BY column_name;
