colaciones = env["step.colacion.registration"].get_dashboard_data("2026-06")
assert colaciones["selected_period"] == "2026-06"
assert colaciones["periods"]
assert all("value" in option and "label" in option for option in colaciones["periods"])
assert "total_period" in colaciones

payroll = env["hr.payslip"].get_steps_payroll_dashboard("2026-06")
assert payroll["selected_period"] == "2026-06"
assert payroll["periods"]
assert payroll["engine"]

print(
    "DASHBOARDS_OK",
    env.cr.dbname,
    "colaciones_periods=", len(colaciones["periods"]),
    "colaciones_total=", colaciones["total_period"],
    "payroll_periods=", len(payroll["periods"]),
    "payroll_total=", payroll["total"],
    "engine=", payroll["engine"],
)
