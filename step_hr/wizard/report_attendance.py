# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
import io
import base64
import calendar
import math

from odoo.tools.misc import xlsxwriter
from odoo.exceptions import UserError, ValidationError

class ReportStepHrsWizard(models.TransientModel):
    _name = 'report.step.hrs.wizard'
    _description = 'Reporte de horas xls'
    _check_company_auto = True

    def _compute_file_name(self):
        for rec in self:
            rec.file_name = 'reporte_Labores_por_trabajador.xlsx'

    employee_ids = fields.Many2many(
        'hr.employee', 'employee_wizard_rel', 'employee_id', 'wizard_id', string='Empleados')
    all_employees = fields.Boolean(string="Todos los empleados", default=False)
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)

    # Resultado
    file = fields.Binary(string='Archivo')
    file_name = fields.Char(string='Nombre', compute='_compute_file_name')


    def quitar_letras(self, codigo):
        new_code = ''
        for cod in str(codigo):
            if cod.isdigit():
                new_code = str(new_code) + str(cod)
        return new_code

    def generate_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Formatos de celda
        merge_format = workbook.add_format({
            'bold': True,
            'border': 6,
            'align': 'center',
            'valign': 'vcenter',
            'fg_color': '#D7E4BC',
        })
        title_format = workbook.add_format({'bg_color': '#87CEEB', 'bold': True, 'border': 0, 'align': 'left'})
        header = workbook.add_format({'bold': True, 'border': 1, 'align': 'center'})
        numerico_cant = workbook.add_format({'border': 0, 'align': 'right', 'num_format': f'#,##0.{(1) * "0"}'})
        numerico_price = workbook.add_format({'border': 0, 'align': 'right', 'num_format': f'#,##0.{(2) * "0"}'})
        caracteres = workbook.add_format({'border': 0, 'align': 'left'})

        # Cabeceras
        worksheet.write_string('A1:A1', 'Nombre registro', title_format)
        worksheet.write_string('B1:C1', 'Tipo Tarea', title_format)
        worksheet.write_string('C1:C1', 'Propio', title_format)
        worksheet.write_string('D1:D1', 'Contratista', title_format)
        worksheet.write_string('E1:E1', 'Cuadrilla', title_format)
        worksheet.write_string('F1:F1', 'Labor/Tarea', title_format)
        worksheet.write_string('G1:G1', 'Supervisor', title_format)
        worksheet.write_string('H1:H1', 'Centro costos', title_format)
        worksheet.write_string('I1:I1', 'Cuartel', title_format)
        worksheet.write_string('J1:J1', 'Variedad', title_format)
        worksheet.write_string('K1:K1', 'UdM', title_format)
        worksheet.write_string('L1:L1', 'Fecha', title_format)
        worksheet.write_string('M1:M1', 'Folio (OT)', title_format)
        worksheet.write_string('N1:N1', 'Responsable', title_format)
        worksheet.write_string('O1:O1', 'Fundo', title_format)
        worksheet.write_string('P1:P1', 'Tarifa', title_format)
        worksheet.write_string('Q1:Q1', 'Especie', title_format)
        worksheet.write_string('R1:R1', 'Grupo Variedad', title_format)
        worksheet.write_string('S1:S1', 'Empresa', title_format)
        worksheet.write_string('T1:T1', 'Empleado', title_format)
        worksheet.write_string('U1:U1', 'NIP', title_format)
        worksheet.write_string('V1:V1', 'Cantidad', title_format)
        worksheet.write_string('W1:W1', 'Hrs ord', title_format)
        worksheet.write_string('X1:X1', 'Hrs Extra', title_format)
        worksheet.write_string('Y1:Y1', 'Total Hrs.', title_format)
        worksheet.write_string('Z1:Z1', 'Cant Mínima', title_format)
        worksheet.write_string('AA1:AA1', 'Tarifa', title_format)
        worksheet.write_string('AB1:AB1', 'Total Trato', title_format)
        worksheet.write_string('AC1:AC1', 'Sueldo base', title_format)
        worksheet.write_string('AD1:AD1', 'Valor Hr Extra', title_format)
        worksheet.write_string('AE1:AE1', 'Variable trato', title_format)
        worksheet.write_string('AF1:AF1', 'Sem Corrida', title_format)
        worksheet.write_string('AG1:AG1', 'Sab-Dom', title_format)
        worksheet.write_string('AH1:AH1', 'Gratificación', title_format)
        worksheet.write_string('AI1:AI1', 'Costo sueldo', title_format)
        worksheet.write_string('AJ1:AJ1', 'Seguro', title_format)
        worksheet.write_string('AK1:AK1', 'Feriado', title_format)
        worksheet.write_string('AL1:AL1', 'IAS', title_format)
        worksheet.write_string('AM1:AM1', 'Costo Empresa', title_format)
        # worksheet.write_string('AN1:AN1', 'Costo por UdM', title_format)

        # Ancho de las columnas
        worksheet.set_column('A:AX', 15)
        # Data
        if self.all_employees:
            result = self.env['step.tarja.line'].search(
                [('date', '>=', (self.date_from)),
                 ('date', '<=', (self.date_to))]
            )
        else:
            result = self.env['step.tarja.line'].search(
                [('date', '>=', (self.date_from)),
                 ('date', '<=', (self.date_to)),
                 ('employee_id', 'in', self.employee_ids.ids)]
            )
        result2 = False
        # result2 = self.env['step.tarja.cost.line'].search([]
        #     # [('invoice_date', '>=', (inicio_mes)),
        #     #  ('invoice_date', '<=', (fin_mes)),
        #     #  ('move_type', '=', 'out_invoice')]
        # )
        # sql = """
        #     select rp.name, count(*)
        #     from account_move cm
        #              inner join res_partner rp on cm.partner_id = rp.id
        #     group by rp.name
        # """
        # self.env.cr.execute(sql)
        # result = self.env.cr.fetchall()

        # Logica
        row = 1
        total = 0
        first_row = row
        end_row = row
        for tarja in result:
            worksheet.write_string(row, 0, tarja.tarja_id.name or '', caracteres)
            worksheet.write_string(row, 1, '', caracteres)
            worksheet.write_string(row, 2, tarja.tarja_id.tarja_type or '', caracteres)
            worksheet.write_string(row, 3, '', caracteres)
            worksheet.write_string(row, 4, tarja.tarja_id.salary_id.name or '', caracteres)
            worksheet.write_string(row, 5, tarja.labor_id.name or '', caracteres)
            worksheet.write_string(row, 6, tarja.tarja_id.super_id.name or '', caracteres)
            worksheet.write_string(row, 7, tarja.cost_id.name or '', caracteres)
            worksheet.write_string(row, 8, '', caracteres)
            worksheet.write_string(row, 9, tarja.cost_id.variedad_id.name or '', caracteres)
            worksheet.write_string(row, 10, tarja.uom_id.name or '', caracteres)
            worksheet.write_string(row, 11, str(tarja.tarja_id.date) or '', caracteres)
            worksheet.write_string(row, 12, tarja.tarja_id.folio or '', caracteres)
            worksheet.write_string(row, 13, '', caracteres)
            worksheet.write_string(row, 14, tarja.tarja_id.fundo_id.name or '', caracteres)
            worksheet.write_string(row, 15, tarja.tarja_id.pricelist_id.name or '', caracteres)
            worksheet.write_string(row, 16, tarja.tarja_id.especie_id.name or '', caracteres)
            worksheet.write_string(row, 17, '', caracteres)
            worksheet.write_string(row, 18, tarja.tarja_id.company_id.name or '', caracteres)
            worksheet.write_string(row, 19, tarja.employee_id.name or '', caracteres)
            worksheet.write_string(row, 20, tarja.employee_id.pin or '', numerico_cant)
            worksheet.write_number(row, 21, tarja.quantity or 0, numerico_price)
            worksheet.write_number(row, 22, tarja.hrs or 0, numerico_price)
            worksheet.write_number(row, 23, tarja.hrs_extra or 0, numerico_price)
            worksheet.write_number(row, 24, tarja.hrs_total or 0, numerico_price)
            worksheet.write_number(row, 25, tarja.cant_minima or 0, numerico_price)
            worksheet.write_number(row, 26, tarja.tarifa or 0, numerico_price)
            worksheet.write_number(row, 27, tarja.total_trato or 0, numerico_cant)
            worksheet.write_number(row, 28, tarja.sueldo_base or 0, numerico_cant)
            worksheet.write_number(row, 29, tarja.valor_hrs_extra or 0, numerico_cant)
            worksheet.write_number(row, 30, tarja.variable_trato or 0, numerico_cant)
            worksheet.write_number(row, 31, tarja.sem_corrida or 0, numerico_cant)
            worksheet.write_number(row, 32, tarja.sab_dom or 0, numerico_cant)
            worksheet.write_number(row, 33, tarja.gratifica or 0, numerico_cant)
            worksheet.write_number(row, 34, tarja.cost_sueldo or 0, numerico_cant)
            worksheet.write_number(row, 35, tarja.seguro or 0, numerico_cant)
            worksheet.write_number(row, 36, tarja.feriado or 0, numerico_cant)
            worksheet.write_number(row, 37, tarja.ias or 0, numerico_cant)
            worksheet.write_number(row, 38, tarja.cost_empresa or 0, numerico_cant)
            # total += line[1]
            row += 1
            end_row = row
        # for tarja in result2:
        #     worksheet.write_string(row, 0, tarja.tarja_cost_id.name or '', caracteres)
        #     worksheet.write_string(row, 1, '', caracteres)
        #     worksheet.write_string(row, 2, '', caracteres)
        #     worksheet.write_string(row, 3, tarja.tarja_cost_id.tarja_type or '', caracteres)
        #     worksheet.write_string(row, 4, tarja.tarja_cost_id.salary_id_contrac.name or '', caracteres)
        #     worksheet.write_string(row, 5, tarja.labor_id.name or '', caracteres)
        #     worksheet.write_string(row, 6, tarja.tarja_cost_id.super_id.name or '', caracteres)
        #     worksheet.write_string(row, 7, tarja.cost_id.name or '', caracteres)
        #     worksheet.write_string(row, 8, '', numerico)
        #     worksheet.write_string(row, 9, tarja.cost_id.variedad_id.name or '', caracteres)
        #     worksheet.write_string(row, 10, tarja.uom_id.name or '', caracteres)
        #     worksheet.write_string(row, 11, str(tarja.tarja_cost_id.date) or '', numerico)
        #     worksheet.write_string(row, 12, tarja.tarja_cost_id.folio or '', caracteres)
        #     worksheet.write_string(row, 13, '', caracteres)
        #     worksheet.write_string(row, 14, tarja.tarja_cost_id.fundo_id.name or '', caracteres)
        #     worksheet.write_string(row, 15, tarja.tarja_cost_id.pricelist_id.name or '', caracteres)
        #     worksheet.write_string(row, 16, tarja.tarja_cost_id.especie_id.name or '', caracteres)
        #     worksheet.write_string(row, 17, '', caracteres)
        #     worksheet.write_string(row, 18, tarja.tarja_cost_id.company_id.name or '', caracteres)
        #     worksheet.write_string(row, 19, tarja.employee_id.name or '', caracteres)
        #     worksheet.write_string(row, 20, tarja.employee_id.pin or '', caracteres)
        #     worksheet.write_number(row, 21, tarja.quantity or 0, numerico)
        #     worksheet.write_number(row, 22, tarja.hrs or 0, numerico)
        #     worksheet.write_string(row, 23, '', caracteres)
        #     worksheet.write_string(row, 24, '', numerico)
        #     worksheet.write_number(row, 25, tarja.cant_minima or 0, numerico)
        #     worksheet.write_number(row, 26, tarja.tarifa or 0, numerico)
        #     worksheet.write_number(row, 27, tarja.trato_total or 0, numerico)
        #     worksheet.write_string(row, 28, '', caracteres)
        #     worksheet.write_string(row, 29, '', caracteres)
        #     worksheet.write_string(row, 30, '', caracteres)
        #     worksheet.write_string(row, 31, '', caracteres)
        #     worksheet.write_string(row, 32, '', caracteres)
        #     worksheet.write_string(row, 33, '', caracteres)
        #     worksheet.write_string(row, 34, '', caracteres)
        #     worksheet.write_string(row, 35, '', caracteres)
        #     worksheet.write_string(row, 36, '', caracteres)
        #     worksheet.write_string(row, 37, '', caracteres)
        #     worksheet.write_string(row, 38, '', caracteres)
        #     # total += line[1]
        #     row += 1
        #     end_row = row

        # Total
        # worksheet.write_string(row, 1, 'Total:', numerico)
        # worksheet.write_number(row, 2, total, numerico)
        # worksheet.write_formula(row, 3, f'SUM(C{first_row + 1}:C{row})', numerico)

        workbook.close()
        output.seek(6)
        self.write({
            'file': base64.b64encode(output.getvalue()),
        })
        return {
            'name': 'Labores por trabajador propio',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'target': 'new'
        }