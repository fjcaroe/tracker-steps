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
        self.ensure_one()
        if not self.user_ids:
            raise ValidationError(_('Seleccione empleados antes de importar.'))
        self.payslip_run_id.check_access('read')
        self.struct_id.check_access('read')
        self.input_type_id.check_access('read')
        if self.payslip_run_id.company_id != self.env.company:
            raise ValidationError(_('El lote debe pertenecer a la empresa activa.'))
        if self.input_type_id.struct_ids and self.struct_id not in self.input_type_id.struct_ids:
            raise ValidationError(_('El tipo de entrada no corresponde a la estructura seleccionada.'))

        # Resolve the complete batch before creating anything. Never choose the
        # first contract/payslip or fall back to another period, company or state.
        slips = self.env['hr.payslip']
        for user in self.user_ids:
            employee = user.employee_id
            if not employee or employee.company_id != self.env.company:
                raise ValidationError(_('Cada usuario debe tener un empleado en la empresa activa.'))
            matches = self.env['hr.payslip'].search([
                ('employee_id', '=', employee.id),
                ('company_id', '=', self.env.company.id),
                ('payslip_run_id', '=', self.payslip_run_id.id),
                ('struct_id', '=', self.struct_id.id),
            ], limit=2)
            if len(matches) != 1 or matches in slips:
                raise ValidationError(_('Debe existir una única liquidación por empleado, lote y estructura.'))
            matches.check_access('write')
            slips |= matches

        # Serialize imports with native payroll state changes on the same rows.
        # Access checks above and ORM create below retain the original ACL/rules.
        self.env.cr.execute('SELECT id FROM hr_payslip_run WHERE id=%s FOR UPDATE',
                            [self.payslip_run_id.id])
        self.env.cr.execute('SELECT id FROM hr_payslip WHERE id IN %s ORDER BY id FOR UPDATE',
                            [tuple(slips.ids)])
        self.payslip_run_id.invalidate_recordset(['state'])
        slips.invalidate_recordset()
        if self.payslip_run_id.state != 'draft':
            raise ValidationError(_('Solo se pueden importar entradas en lotes en borrador.'))
        values = []
        for slip in slips:
            slip.check_access('write')
            if (slip.state != 'draft' or slip.paid or
                    slip.payslip_run_id != self.payslip_run_id or slip.struct_id != self.struct_id or
                    slip.company_id != self.env.company or slip.employee_id not in self.user_ids.employee_id):
                raise ValidationError(_('Solo se pueden modificar liquidaciones en borrador, no pagadas, del lote y estructura seleccionados.'))
            contract = slip.contract_id
            if not contract or contract.employee_id != slip.employee_id or contract.company_id != slip.company_id:
                raise ValidationError(_('La liquidación debe conservar su contrato y empleado de la misma empresa.'))
            if slip.input_line_ids.filtered(lambda line: line.input_type_id == self.input_type_id):
                raise ValidationError(_('La liquidación ya tiene una entrada de este tipo; revise el registro existente.'))
            values.append({'name': 'Entrada de Bonos o Descuentos masivos',
                           'payslip_id': slip.id, 'input_type_id': self.input_type_id.id,
                           'amount': self.value_amount, 'contract_id': contract.id})
        self.env['hr.payslip.input'].create(values)
        return self.success_message(len(values))


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
