# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
import io
import base64
import calendar
import math

from odoo.tools.misc import xlsxwriter
from odoo.exceptions import UserError, ValidationError

class ReportBudaSaleWizard(models.TransientModel):
    _name = 'report.buda.sale.wizard'
    _description = 'Reporte de Ventas xls'
    _check_company_auto = True

    def _compute_file_name(self):
        for rec in self:
            rec.file_name = 'reporte_ventas.xlsx'

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
            'border': 6,
            'align': 'center',
            'valign': 'vcenter',
            'fg_color': '#D7E4BC',
        })
        title_format = workbook.add_format({'bold': True, 'border': 0, 'align': 'left'})
        header = workbook.add_format({'bold': True, 'border': 1, 'align': 'center'})
        numerico = workbook.add_format({'border': 0, 'align': 'right'})
        caracteres = workbook.add_format({'border': 0, 'align': 'left'})

        # Cabeceras
        worksheet.write_string('A1:A1', 'RUC', title_format)
        worksheet.write_string('B1:C1', 'ID', title_format)
        worksheet.write_string('C1:C1', 'Periodo', title_format)
        worksheet.write_string('D1:D1', 'CAR SUNAT', title_format)
        worksheet.write_string('E1:E1', 'Fecha de Emisión', title_format)
        worksheet.write_string('F1:F1', 'Fecha Vcto/Pago', title_format)
        worksheet.write_string('G1:G1', 'Tipo CP/Doc', title_format)
        worksheet.write_string('H1:H1', 'Serie del CDP', title_format)
        worksheet.write_string('I1:I1', 'Nro CP o Doc Nro Inicial (Rango)', title_format)
        worksheet.write_string('J1:J1', 'Nro Final (Rango)', title_format)
        worksheet.write_string('K1:K1', 'Tipo Doc Identidad', title_format)
        worksheet.write_string('L1:L1', 'Nro Doc Identidad', title_format)
        worksheet.write_string('M1:M1', 'Apellidos Nombres / Razón Social', title_format)
        worksheet.write_string('N1:N1', 'Valor Facturado Exportación', title_format)
        worksheet.write_string('O1:O1', 'BI Gravada', title_format)
        worksheet.write_string('P1:P1', 'Dscto BI', title_format)
        worksheet.write_string('Q1:Q1', 'IGV/IPM', title_format)
        worksheet.write_string('R1:R1', 'Dscto IGV/IPM', title_format)
        worksheet.write_string('S1:S1', 'Mto Exonerado', title_format)
        worksheet.write_string('T1:T1', 'Mto Inafecto', title_format)
        worksheet.write_string('U1:U1', 'ISC', title_format)
        worksheet.write_string('V1:V1', 'BI Grav IVAP', title_format)
        worksheet.write_string('W1:W1', 'IVAP', title_format)
        worksheet.write_string('X1:X1', 'ICBPER', title_format)
        worksheet.write_string('Y1:Y1', 'Otros Tributos', title_format)
        worksheet.write_string('Z1:Z1', 'Total CP', title_format)
        worksheet.write_string('AA1:AA1', 'Moneda', title_format)
        worksheet.write_string('AB1:AB1', 'Tipo Cambio', title_format)
        worksheet.write_string('AC1:AC1', 'Fecha Emisión Doc Modificado', title_format)
        worksheet.write_string('AD1:AD1', 'Tipo CP Modificado', title_format)
        worksheet.write_string('AE1:AE1', 'Serie CP Modificado', title_format)
        worksheet.write_string('AG1:AG1', 'ID Proyecto Operadores Atribución', title_format)
        worksheet.write_string('AG1:AG1', 'ID Proyecto Operadores Atribución', title_format)
        worksheet.write_string('AH1:AH1', 'CLU 1', title_format)
        worksheet.write_string('AI1:AI1', 'CLU 2', title_format)
        worksheet.write_string('AJ1:AJ1', 'CLU 3', title_format)
        worksheet.write_string('AK1:AK1', 'CLU 4', title_format)
        worksheet.write_string('AL1:AL1', 'CLU 5', title_format)
        worksheet.write_string('AM1:AM1', 'CLU 6', title_format)
        worksheet.write_string('AN1:AN1', 'CLU 7', title_format)
        worksheet.write_string('AO1:AO1', 'CLU 8', title_format)
        worksheet.write_string('AP1:AP1', 'CLU 9', title_format)
        worksheet.write_string('AQ1:AQ1', 'CLU 10', title_format)
        worksheet.write_string('AR1:AR1', 'CLU 11', title_format)
        worksheet.write_string('AS1:AS1', 'CLU 12', title_format)
        worksheet.write_string('AT1:AT1', 'CLU 13', title_format)
        worksheet.write_string('AU1:AU1', 'CLU 14', title_format)
        worksheet.write_string('AV1:AV1', 'CLU 15', title_format)
        worksheet.write_string('AW1:AW1', 'CLU 16', title_format)
        worksheet.write_string('AX1:AX1', 'CLU 17', title_format)

        # Ancho de las columnas
        worksheet.set_column('A:AX', 15)

        # Data
        inicio_mes = str(self.anio_select) + '-' + str(self.mes_select).zfill(2) + '-' + '01'
        ultimo_de_mes = calendar.monthrange(int(self.anio_select), int(self.mes_select))
        fin_mes = str(self.anio_select) + '-' + str(self.mes_select).zfill(2) + '-' + str(ultimo_de_mes[1])
        result = self.env['account.move'].search(
            [('invoice_date', '>=', (inicio_mes)),
             ('invoice_date', '<=', (fin_mes)),
             ('move_type', '=', 'out_invoice')]
        )
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
        for factura in result:
            worksheet.write_string(row, 0, factura.company_id.vat or '', numerico)
            worksheet.write_string(row, 1, factura.company_id.name or '', caracteres)
            worksheet.write_string(row, 2, str(self.anio_select) + str(self.mes_select), numerico)
            worksheet.write_string(row, 3,
                                   str(factura.company_id.vat).rstrip() + str(factura.l10n_latam_document_type_id.code).rstrip() + str(
                                       factura.x_studio_serie_cliente).rstrip() + str(self.quitar_letras(factura.name)).rstrip().zfill(10),
                                   caracteres)
            worksheet.write_string(row, 4, str(factura.invoice_date) or '', numerico)
            worksheet.write_string(row, 5, '', numerico)
            worksheet.write_number(row, 6, int(factura.l10n_latam_document_type_id.code), numerico)
            worksheet.write_string(row, 7, str(factura.x_studio_serie_cliente), caracteres)
            worksheet.write_string(row, 8, str(self.quitar_letras(factura.name)).rstrip() or '', numerico)
            worksheet.write_string(row, 9, '', caracteres) # Nro Final (Rango)
            worksheet.write_string(row, 10, str(factura.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code) or 0, numerico)  # Tipo doc Identidad
            worksheet.write_string(row, 11, str(factura.partner_id.vat) or '', numerico)  # Nro Doc Identidad
            worksheet.write_string(row, 12, str(factura.partner_id.name) or '', caracteres)  # Apellidos Nombres / Razón Social
            worksheet.write_number(row, 13, 0, numerico)  #
            worksheet.write_number(row, 14, factura.amount_untaxed, numerico)  # Valor Facturado Exportación
            worksheet.write_number(row, 15, 0, numerico)  # Dscto BI
            worksheet.write_number(row, 16, factura.amount_tax, numerico)  # IGV/IPM
            worksheet.write_number(row, 17, 0, numerico)  # Dscto IGV/IPM
            worksheet.write_number(row, 18, 0, numerico)  #
            worksheet.write_number(row, 19, 0, numerico)  #
            worksheet.write_number(row, 20, 0, numerico)  #
            worksheet.write_number(row, 21, 0, numerico)  #
            worksheet.write_number(row, 22, 0, numerico)  #
            worksheet.write_number(row, 23, 0, numerico)  #
            worksheet.write_number(row, 24, 0, numerico)  #
            worksheet.write_number(row, 25, factura.amount_total, numerico)  # Total CP
            worksheet.write_string(row, 26, factura.currency_id.name, caracteres)  # Moneda
            worksheet.write_number(row, 27, 1, numerico)  # Tipo Cambio
            worksheet.write_string(row, 28, '', caracteres) # Fecha Emisión Doc Modificado
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
            'name': 'Resultado_' + str(self.anio_select) + '_' + str(self.mes_select),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'target': 'new'
        }