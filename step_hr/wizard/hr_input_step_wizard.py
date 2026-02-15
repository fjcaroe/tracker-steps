# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import binascii
import certifi
import csv
import tempfile
import urllib3
import xlrd
from odoo import fields,models, _
import base64
import openpyxl
from datetime import datetime
from io import BytesIO
from odoo.exceptions import UserError, ValidationError, RedirectWarning
from odoo.tools import ustr

class HrInputStep(models.TransientModel):
    _name = 'hr.input.step.wizard'
    _description = 'Entrada de Bonos o Descuentos masivos'
    _check_company_auto = True

    #name = fields.Char('Nombre')
    payslip_run_id = fields.Many2one('hr.payslip.run', string="Lote", required=True)
    struct_id = fields.Many2one('hr.payroll.structure', string="Estructura Salarial", required=True)
    input_type_id = fields.Many2one('hr.payslip.input.type', string='Tipo', required=True)
    user_ids = fields.Many2many(comodel_name='res.users', relation='step_hr_payslip_rel', string='Empleados')
    value_amount = fields.Float(string='Monto')

    def import_button(self):
        rec_count = 0
        input_obj = self.env['hr.payslip.input']
        contract_obj = self.env['hr.contract']
        if self.user_ids:
            for input in self.user_ids:
                #try:
                    contract_id = contract_obj.search([('employee_id', '=', input.employee_id.id)], limit=1)
                    payslip_id = self.env['hr.payslip'].search([('employee_id', '=', input.employee_id.id)], limit=1)
                    vals = {
                        'name': 'Entrada de Bonos o Descuentos masivos',
                        'payslip_id': payslip_id.id,
                        'input_type_id': self.input_type_id.id,
                        # 'code': ,
                        'amount': self.value_amount,
                        'contract_id': contract_id.id,
                    }
                    input_id = input_obj.create(vals)
                    rec_count += 1

                # except Exception:
                #     raise ValidationError(_("Por favor contacte al Adiminstrador"))
        return self.success_message(rec_count)


    def success_message(self, rec_count):
        """function for displaying success message"""
        message_id = self.env['success.message'].create(
            {'message': str(rec_count) + " Registros Generados exitosamente."})
        return {
            'name': 'Otras Entradas y Descuentos',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'success.message',
            'res_id': message_id.id,
            'target': 'new'
        }