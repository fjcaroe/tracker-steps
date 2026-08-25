SELECT name, state, COALESCE(latest_version, '')
FROM ir_module_module
WHERE name IN (
    'step_hr_contract_lifecycle',
    'step_hr_remuneration_book',
    'step_colaciones',
    'step_demo_homepage',
    'step_agricultural_branding',
    'l10n_cl_hr',
    'l10n_cl_simpledigital_payroll',
    'hr_payroll',
    'step_hr'
)
ORDER BY name;

SELECT v.id, COALESCE(d.module || '.' || d.name, ''), v.name, v.active,
       COALESCE(v.inherit_id::text, ''), LEFT(v.arch_db::text, 300)
FROM ir_ui_view v
LEFT JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id
WHERE d.module = 'l10n_cl_hr' OR d.name = 'report_payslip'
ORDER BY d.module, d.name;
