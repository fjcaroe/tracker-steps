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

class HrEntryXlsWizard(models.TransientModel):
    _name = 'hr.entry.xls.wizard'
    _description = 'Carga Masiva de entradas por excel'
    _check_company_auto = True

    file_data = fields.Binary('Archivo', required=True, )
    file_name = fields.Char('File Name')


    def quitar_letras(self, codigo):
        new_code = ''
        for cod in str(codigo):
            if cod.isdigit():
                new_code = str(new_code) + str(cod)
        return new_code

    def import_button(self):
        sale_order_obj = self.env['sale.order']
        product_obj = self.env['product.product']
        product_template_obj = self.env['product.template']
        sale_order_line_obj = self.env['sale.order.line']
        try:
            file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            file.write(binascii.a2b_base64(self.file_data))
            file.seek(0)
            values = {}
            workbook = xlrd.open_workbook(file.name)
            sheet = workbook.sheet_by_index(0)
        except Exception:
            raise ValidationError(_("Seleccione un formato de archivo válido!"))
        rec_count = 0
        for row_no in range(sheet.nrows):
            val = {}
            if row_no <= 0:
                fields = list(map(lambda row: row.value.encode('utf-8'), sheet.row(row_no)))
            else:
                line = list(
                    map(lambda row: isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value),
                        sheet.row(row_no)))
                rec_count += 1
                ref = int(float(line[0]))
                partner = self.env['res.partner'].search([('ref', '=', ref), ('cod_medidor', '=', line[2])], limit=1)
                if not partner:
                    raise UserError(_('Disculpe, No se puede avanzar con el Registro, \n \n  Porque no se encuentra el cliente: '+str(line[4])+', \n \n Por favor comuniquese con un Administrador'))
                anterior_apr = 0
                actual_apr = False
                ultima_fecha = False
                fecha_e = False
                if partner.res_history_ids:
                    ultimo = partner.res_history_ids[-1]
                    anterior_apr = ultimo.actual_apr
                    ultima_fecha = ultimo.date_hasta
                if line[7]:
                    # fecha_str = "08-09-2025"
                    formato = "%d-%m-%Y"
                    try:
                        fecha_e = datetime.strptime(line[7], formato)
                    except ValueError:
                        raise UserError(
                            _('Disculpe, No se puede avanzar con el Registro, \n \n  Porque la fecha emision no corresponde al formato (%d-%m-%Y) \n \n Por favor comuniquese con un Administrador'))
                # if line[8]:
                #     anterior_apr = float(line[8])
                if line[9]:
                    actual_apr = float(line[9])
                # if anterior_apr.month == actual_apr.month:
                #     raise UserError(
                #         _('Disculpe, No se puede avanzar con el Registro, \n \n  Porque ya se ha registrado una lectura para este mes \n \n Por favor comuniquese con un Administrador'))
                vals = {
                    'partner_id': partner.id,
                    'date_emision': datetime.today().date(),
                    'anterior_apr': anterior_apr,
                    'actual_apr': actual_apr,
                    'p_desde': fecha_e,
                    'p_hasta': ultima_fecha,
                    'carga_type': 'excel',
                    #'state': 'sale',
                }
                sale_order_id = sale_order_obj.create(vals)
                if sale_order_id: #and product_id:
                    if sale_order_id.company_id.product_fijo:
                        vals_f = {
                            'order_id': sale_order_id.id,
                            'product_id': sale_order_id.company_id.product_fijo.id,
                            'product_uom_qty': 1,
                        }
                        sale_order_fijo = sale_order_line_obj.create(vals_f)
                        if partner.client_type == 'socio':
                            sale_order_fijo.write({'tax_id': False})
                    if sale_order_id.company_id.product_consu:
                        vals_c = {
                            'order_id': sale_order_id.id,
                            'product_id': sale_order_id.company_id.product_consu.id,
                            'product_uom_qty': float(sale_order_id.consumo_apr),
                        }
                        sale_order_consu = sale_order_line_obj.create(vals_c)
                        if partner.client_type == 'socio':
                            sale_order_consu.write({'tax_id': False})
        # return {'type': 'ir.actions.act_window_close'}
        return self.success_message(rec_count)

    def success_message(self, rec_count):
        """function for displaying success message"""
        message_id = self.env['success.message'].create(
            {'message': str(rec_count) + " Registros importados exitosamente."})
        return {
            'name': 'Carga APR',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'success.message',
            'res_id': message_id.id,
            'target': 'new'
        }