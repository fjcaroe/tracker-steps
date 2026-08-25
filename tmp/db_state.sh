#!/usr/bin/env bash
set -eu

for db_name in LAB_TAREAS STEPS_DEMO STEPS_DEMO_SYS; do
    echo "--- $db_name"
    sudo -u postgres psql -d "$db_name" -AtF '|' -c "
        SELECT name, state, COALESCE(latest_version, '')
        FROM ir_module_module
        WHERE name IN (
            'step_hr_contract_lifecycle',
            'step_hr_remuneration_book',
            'step_colaciones',
            'step_agricultural_branding',
            'step_demo_homepage',
            'hr_work_entry_contract_enterprise',
            'website',
            'hr_attendance',
            'account',
            'analytic'
        )
        ORDER BY name;
    "
    sudo -u postgres psql -d "$db_name" -AtF '|' -c "
        SELECT 'companies', count(*) FROM res_company
        UNION ALL SELECT 'employees', count(*) FROM hr_employee
        UNION ALL SELECT 'payslips', count(*) FROM hr_payslip
        UNION ALL SELECT 'meal_registrations', count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='step_meal_registration';
    " || true
done
