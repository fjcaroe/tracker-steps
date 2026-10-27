"""Fail closed before upgrading an existing payroll HR installation alone."""
from odoo.exceptions import UserError


def require_payroll_bridge(cr):
    cr.execute("SELECT name,state FROM ir_module_module WHERE name IN ('hr_payroll','step_hr_payroll_bridge')")
    states=dict(cr.fetchall())
    if states.get('hr_payroll') in ('installed','to upgrade') and states.get('step_hr_payroll_bridge') not in ('installed','to install','to upgrade'):
        raise UserError('La actualización de HR con Nómina existente requiere instalar step_hr_payroll_bridge en el mismo paquete; se conservan el tipo bancario y los contratos de Nómina.')
