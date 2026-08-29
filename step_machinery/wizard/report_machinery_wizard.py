# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
import io
import base64
import calendar
import math

from odoo.tools.misc import xlsxwriter
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date, formatLang
from odoo.tools.float_utils import float_repr
from odoo.tools import groupby

from collections import defaultdict
from markupsafe import Markup, escape
from odoo.tools import frozendict
import json

class ReportMachineryWizard(models.TransientModel):
    _name = 'report.machinery.wizard'
    _description = 'Reporte de Maquinarias xls'
    _check_company_auto = True

    def _compute_file_name(self):
        for rec in self:
            rec.file_name = 'reporte_maquinarias.xlsx'

    # Parámetros
    mes_select = fields.Selection(
        [('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'), ('04', 'Abril'), ('05', 'Mayo'),
         ('06', 'Junio'), ('07', 'Julio'), ('08', 'Agosto'), ('09', 'Septiembre'),
         ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')], string='Mes', required=True)
    anio_select = fields.Char(string="Año", required=True, default='2025')
    # Resultado
    file = fields.Binary(string='File')
    file_name = fields.Char(string='File Name', compute='_compute_file_name')

    def quitar_letras(self, codigo):
        new_code = ''
        for cod in str(codigo):
            if cod.isdigit():
                new_code = str(new_code) + str(cod)
        return new_code

    def generate_report(self):
        if not self.anio_select.isdigit():
            raise ValidationError(_("Ingresar valores correctos en los parametros."))
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Formatos de celda
        merge_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            #'fg_color': '#D7E4BC',
        })
        title_format = workbook.add_format({'bold': True, 'border': 0, 'align': 'left'})
        header = workbook.add_format({'bold': True, 'border': 1, 'align': 'center'})
        numerico = workbook.add_format({'border': 0, 'align': 'right'})
        caracteres = workbook.add_format({'border': 0, 'align': 'left'})

        # Cabeceras
        worksheet.write_string('A1:A1', 'MES', title_format)
        worksheet.write_string('B1:C1', 'MAQUINA', title_format)
        worksheet.write_string('C1:C1', 'ASIENTO CONTABLE', title_format)
        worksheet.write_string('D1:D1', 'FECHA', title_format)
        worksheet.write_string('E1:E1', 'NUM DOCUMENTO', title_format)
        worksheet.write_string('F1:F1', 'PROVEEDOR', title_format)
        worksheet.write_string('G1:G1', 'CUENTA CONTABLE', title_format)
        worksheet.write_string('H1:H1', 'CONCEPTO MAQUINA', title_format)
        worksheet.write_string('I1:I1', 'PRODUCTO', title_format)
        worksheet.write_string('J1:J1', 'CENTRO COSTO FINAL', title_format)
        worksheet.write_string('K1:K1', 'FUNDO', title_format)
        worksheet.write_string('L1:L1', 'LABOR MAQUINARIA', title_format)
        worksheet.write_string('M1:M1', 'ACTIVIDAD', title_format)
        worksheet.write_string('N1:N1', 'MONTO NETO', title_format)

        # Ancho de las columnas
        worksheet.set_column('A:AX', 15)

        # Data
        inicio_mes = str(self.anio_select) + '-' + str(self.mes_select).zfill(2) + '-' + '01'
        ultimo_de_mes = calendar.monthrange(int(self.anio_select), int(self.mes_select))
        fin_mes = str(self.anio_select) + '-' + str(self.mes_select).zfill(2) + '-' + str(ultimo_de_mes[1])
        result = self.env['real.cost.machinery'].search(
            [('date', '>=', (inicio_mes)),
             ('date', '<=', (fin_mes)),
             ('state', '=', 'conta')]
        )

        # Logica
        row = 1
        total = 0
        first_row = row
        for machinery in result:
            worksheet.write_string(row, 0, str(self.mes_select)+'/'+str(self.anio_select) or '', caracteres) # MES
            worksheet.write_string(row, 1, machinery.machinery_ids.name or '', caracteres) # MAQUINA
            worksheet.write_string(row, 2, machinery.invoice_id.ref, caracteres) #ASIENTO CONTABLE
            worksheet.write_string(row, 3, str(machinery.invoice_id.date) or '', caracteres) #FECHA
            worksheet.write_string(row, 4, str(machinery.invoice_id.l10n_latam_document_number) or '', caracteres) #NUM DOCUMENTO
            worksheet.write_string(row, 5, str(machinery.invoice_id[0].partner_id.name) or '', caracteres) # PROVEEDOR
            worksheet.write_string(row, 6, str(machinery.invoice_id[0].account_id.name) or '', caracteres) # CUENTA CONTABLE
            worksheet.write_string(row, 7, str(machinery.service_machinery_id.name) or '', caracteres) # CONCEPTO MAQUINA
            worksheet.write_string(row, 8, '', caracteres) # PRODUCTO
            worksheet.write_string(row, 9, str(machinery.cost_id.name) or '', caracteres)  # CENTRO COSTO FINAL
            worksheet.write_string(row, 10, machinery.fundo_id.name, caracteres)  # FUNDO
            worksheet.write_string(row, 11, str(machinery.labor_id.name) or '', caracteres)  # LABOR MAQUINARIA
            worksheet.write_string(row, 12, str(machinery.labor_id.act.name) or '', numerico)  # ACTIVIDAD
            worksheet.write_string(row, 13, machinery.cost_amount, numerico)  # MONTO NETO
            # total += line[1]
            row += 1

        # Total
        # worksheet.write_string(row, 1, 'Total:', border)
        # worksheet.write_number(row, 2, total, border)
        # worksheet.write_formula(row, 3, f'SUM(C{first_row + 1}:C{row})', border)

        workbook.close()
        output.seek(6)
        self.write({
            'file': base64.b64encode(output.getvalue()),
        })
        return {
            'name': 'Resultado_'+str(self.anio_select)+'_'+str(self.mes_select),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'target': 'new'
        }



