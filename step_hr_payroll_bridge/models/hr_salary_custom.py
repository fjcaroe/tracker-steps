from odoo import fields, models


class HrSalaryCustomPayroll(models.Model):
    _inherit = 'hr.salary.custom'

    payslip_run_id = fields.Many2one('hr.payslip.run', string='Lote', required=False)
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura Salarial', required=False)
