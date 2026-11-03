from textwrap import indent

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    allowances = (
        ("hr_rule_colocation", "payroll_whole_days_meal", "colocation"),
        ("hr_rule_movility", "payroll_whole_days_transport", "movility"),
    )
    for external_id, option, amount in allowances:
        rule = env.ref(f"l10n_cl_simpledigital_payroll.{external_id}")
        condition = f"if payslip.company_id.{option}:"
        original = rule.amount_python_compute
        if original.startswith(condition):
            continue
        if rule.amount_select != "code" or not original or not original.strip():
            raise ValueError(f"Expected a Python formula for {external_id}")
        rule.amount_python_compute = (
            f"{condition}\n"
            f"    result = payslip.step_whole_day_allowance(contract.{amount} or 0.0)\n"
            f"else:\n{indent(original, '    ')}"
        )
