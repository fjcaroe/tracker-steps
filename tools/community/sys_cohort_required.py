"""Preserve physical NOT NULL contracts on the admitted SyS partial graph."""
from preflight_original_history_storage import require


# Original field SQL types, original ORM source modules and mandatory status
# were compared on U33 and on a normally initialized Community payroll cohort.
COLUMNS = {
    ('hr_contract', 'income_tax_type'): ('character varying', 'l10n_cl_simpledigital_payroll'),
    ('hr_contract', 'work_schedule_id'): ('character varying', 'l10n_cl_simpledigital_payroll'),
    ('hr_payroll_structure', 'type_id'): ('integer', 'hr_payroll'),
    ('hr_payslip', 'name'): ('character varying', 'hr_payroll'),
    ('hr_salary_rule', 'category_id'): ('integer', 'hr_payroll'),
    ('hr_salary_rule', 'code'): ('character varying', 'hr_payroll'),
    ('hr_salary_rule_category', 'code'): ('character varying', 'hr_payroll'),
    ('res_company', 'account_tax_periodicity'): ('character varying', 'account_reports'),
    ('res_company', 'account_tax_periodicity_reminder_day'): ('integer', 'account_reports'),
    ('res_company', 'currency_interval_unit'): ('character varying', 'currency_rate_live'),
    ('res_company', 'deferred_expense_amount_computation_method'): ('character varying', 'account_accountant'),
    ('res_company', 'deferred_revenue_amount_computation_method'): ('character varying', 'account_accountant'),
    ('res_company', 'generate_deferred_expense_entries_method'): ('character varying', 'account_accountant'),
    ('res_company', 'generate_deferred_revenue_entries_method'): ('character varying', 'account_accountant'),
    ('res_company', 'planning_employee_unavailabilities'): ('character varying', 'planning'),
    ('res_company', 'planning_generation_interval'): ('integer', 'planning'),
    ('res_company', 'timesheet_mail_employee_interval'): ('character varying', 'timesheet_grid'),
    ('res_company', 'timesheet_mail_interval'): ('character varying', 'timesheet_grid'),
}


def read_original(cr, table, name):
    expected, owner = COLUMNS[table, name]
    cr.execute("""SELECT f.id,format_type(a.atttypid,a.atttypmod),a.attnotnull,d.module
        FROM pg_attribute a JOIN ir_model_fields f ON f.model=%s AND f.name=a.attname
        JOIN ir_model_data d ON d.model='ir.model.fields' AND d.res_id=f.id AND d.module=%s
        WHERE a.attrelid=to_regclass(%s) AND a.attname=%s AND NOT a.attisdropped""",
               (table.replace('_', '.'), owner, 'public.' + table, name))
    rows = cr.fetchall()
    require(len(rows) == 1 and rows[0][1:] == (expected, True, owner),
            'SyS mandatory source column changed: ' + table + '.' + name)
    return rows[0][0]


def inventory(cr):
    return {table + '.' + name: read_original(cr, table, name) for table, name in sorted(COLUMNS)}


def guard(original, database, ids):
    require(set(ids) == {table + '.' + name for table, name in COLUMNS},
            'SyS native mandatory column inventory missing')

    def drop_not_null(cr, table, column):
        if (table, column) not in COLUMNS or cr.dbname != database:
            return original(cr, table, column)
        # The official loader relaxes all unregistered columns when their
        # owning addon is outside the scoped graph. Preserve the original SQL
        # constraint without adding an implementation of the excluded feature.
        require(read_original(cr, table, column) == ids[table + '.' + column],
                'SyS mandatory field identity changed')

    return drop_not_null
