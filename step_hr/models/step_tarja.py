# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import io
import base64
import calendar
import math
from odoo.tools.misc import xlsxwriter
from odoo import api, Command, fields, models, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
from datetime import date, time, datetime

class StepTarja(models.Model):
    _name = 'step.tarja'
    _inherit = ['mail.thread']

    @api.model
    def default_get(self, fields):
        res = super(StepTarja, self).default_get(fields)
        if self.env.context.get('step_default_contratista'):
            res.update({
                'tarja_type': 'contratista'
            })
        if self.env.context.get('step_default_propio'):
            res.update({
                'tarja_type': 'propio'
            })
        return res

    name = fields.Char(string='Nombre', index=True)
    salary_id = fields.Many2one(
        comodel_name='hr.salary.custom',
        string="Cuadrilla",
        required=False, ondelete='cascade')
    salary_id_contrac = fields.Many2one(
        comodel_name='hr.salary.custom',
        string="Cuadrilla Contratista",
        required=False, ondelete='cascade')
    tarja_type = fields.Selection(string='Tipo Tarea',
                                  selection=[('propio', 'Propio'),
                                             ('contratista', 'Contratista')], default='propio')
    partner_id = fields.Many2one('res.partner', 'Contratista')
    folio = fields.Char(string='Orden de Trabajo', index=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, tracking=True, copy=False)
    user_id = fields.Many2one('res.users', 'Usuario', default=lambda self: self.env.user)
    fundo_id = fields.Many2one('step.fundo',
                               string="Fundo",
                               required=False, ondelete='cascade', copy=False)
    super_id = fields.Many2one('hr.employee', 'Supervisor')
    auto_id = fields.Many2one('hr.employee', 'Autorizador')
    company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)
    gratificacion_legal = fields.Boolean(related='company_id.gratificacion_legal')
    sema_corrida_legal = fields.Boolean(related='company_id.sema_corrida_legal')
    note = fields.Html(string="Nota")
    tarja_registry = fields.One2many(
        comodel_name='step.tarja.registry',
        inverse_name='tarja_id',
        string="tarja registry Lines",
        copy=True, auto_join=True)
    tarja_line = fields.One2many(
        comodel_name='step.tarja.line',
        inverse_name='tarja_id',
        string="tarja Lines",
        copy=True, auto_join=True)
    tarja_cost_line = fields.One2many(
        comodel_name='step.tarja.cost.line',
        inverse_name='tarja_cost_id',
        string="tarja Lines",
        copy=True, auto_join=True)
    state = fields.Selection(
        selection=[
            ('in', 'Ingresado'),
            ('auto', 'Autorizado'),
            ('costo', 'Costeo'),
            ('conta', 'Contabilizada'),
            # ('pag', 'Pagada'),
        ],
        string='Estado',
        required=True,
        readonly=False,
        copy=False,
        default='in',
    )
    remunera = fields.Boolean(string='Remuneraciones')
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Tarifa'
    )
    especie_id = fields.Many2one('step.especie', related='pricelist_id.especie_id',
                                 string="Especie",
                                 required=False, ondelete='cascade', copy=False)
    grupo_variedad_id = fields.Many2one('step.grupo.variedad', related='pricelist_id.grupo_variedad_id',
                                        string="Grupo Variedad",
                                        required=False, ondelete='cascade', copy=False)
    grupo_variedad_id_domain = fields.Many2many('step.grupo.variedad', related='pricelist_id.grupo_variedad_id_domain', string='Grupo Variedad')
    invoice_id = fields.Many2one('account.move', string='Contabilización')
    purchase_id = fields.Many2one('purchase.order', string='Orden de Compras')

    @api.onchange('salary_id')
    def onchange_salary_id(self):
        self.ensure_one()
        for record in self:
            if record.salary_id:
                # if record.salary_id.group_type:
                #     record.tarja_type = record.salary_id.group_type
                # else:
                #     record.tarja_type = ''
                # if record.salary_id.folio:
                #     record.folio = record.salary_id.folio
                # else:
                #     record.folio = ''
                if record.salary_id.fundo_id:
                    record.fundo_id = record.salary_id.fundo_id
                else:
                    record.fundo_id = ''
                # if record.salary_id.work_entry_type_id:
                #     record.folio = record.salary_id.work_entry_type_id.id
                # else:
                #     record.folio = ''
                # if record.salary_id.responsable_id:
                #     record.employee_id = record.salary_id.responsable_id.id
                # else:
                #     record.employee_id = ''
                vals = []
                if record.tarja_line:
                    record.tarja_line.unlink()
                if record.salary_id.salary_line:
                    for line in record.salary_id.salary_line:
                        vals.append((0, 0, {
                            'employee_id': line.employee_id.id,
                            'contract_id': self.env['hr.contract'].search(
                                            [('employee_id', '=', line.employee_id.id)], limit=1).id,
                            #'quantity': line.hours,
                        }))
                record.tarja_line = vals

    @api.onchange('salary_id_contrac')
    def onchange_salary_id_contrac(self):
        self.ensure_one()
        for record in self:
            if record.salary_id_contrac:
                # if record.salary_id_contrac.group_type:
                #     record.tarja_type = record.salary_id.group_type
                # else:
                #     record.tarja_type = ''
                # if record.salary_id_contrac.folio:
                #     record.folio = record.salary_id_contrac.folio
                # else:
                #     record.folio = ''
                if record.salary_id_contrac.fundo_id:
                    record.fundo_id = record.salary_id_contrac.fundo_id
                else:
                    record.fundo_id = ''
                # if record.salary_id.work_entry_type_id:
                #     record.folio = record.salary_id.work_entry_type_id.id
                # else:
                #     record.folio = ''
                if record.salary_id_contrac.partner_id:
                    record.partner_id = record.salary_id_contrac.partner_id.id
                else:
                    record.partner_id = ''
                vals = []
                if record.tarja_cost_line:
                    record.tarja_cost_line.unlink()
                if record.salary_id_contrac.contract_line:
                    for line in record.salary_id_contrac.contract_line:
                        vals.append((0, 0, {
                            'employee_id': line.employee_id.id,
                            # 'contract_id': line.contract_id.id,
                            #'quantity': line.hours,
                        }))
                record.tarja_cost_line = vals

    def action_in(self):
        for salary in self:
            salary.write({'state': 'in'})

    def action_auto(self):
        for salary in self:
            salary.write({'state': 'auto'})

    def envio_nomina(self):
        for salary in self:
            specific_time = time(hour=12, minute=00)
            combined_datetime = datetime.combine(salary.date, specific_time)
            salary.write({'remunera': True})
            if salary.tarja_type == 'propio':
                for line in salary.tarja_line:
                    if line.hrs > 0:
                        fecha_hora = salary.date
                        hora_extra = combined_datetime + timedelta(hours=int(line.hrs))
                        work_id = self.env['hr.work.entry'].create([{
                            'name': salary.name + ' - ' + line.labor_id.name,
                            'employee_id': line.employee_id.id,
                            'work_entry_type_id': 1,
                            'date_start': combined_datetime,
                            'date_stop': combined_datetime + timedelta(hours=int(line.hrs)),
                            'duration': line.hrs,
                        }])
                    if line.hrs_extra > 0:
                        work_extra_id = self.env['hr.work.entry'].create([{
                            'name': salary.name + ' - ' + line.labor_id.name,
                            'employee_id': line.employee_id.id,
                            'work_entry_type_id': 2,
                            'date_start': hora_extra,
                            'date_stop': hora_extra + timedelta(hours=int(line.hrs_extra)),
                            'duration': line.hrs_extra,
                        }])

    def action_conta(self):
        for salary in self:
            salary.write({'state': 'conta'})
            if salary.tarja_type == 'contratista':
                line_asiento = []
                total = 0.0
                invoice_id = self.env['account.move'].create([{
                    'ref': self.name,
                    'date': self.date,
                    'move_type': 'entry',
                    'contra': True,
                    'state': 'draft',#'pro',
                    'partner_id': salary.partner_id.id,
                    'journal_id': salary.company_id.step_journal_id.id,
                    'l10n_latam_document_type_id': salary.company_id.step_document_type_id.id,
                }])
                salary.invoice_id = invoice_id.id
                vals = []
                cost_temporada = self.env['step.temporada'].search(
                    [('start_date', '<=', salary.date),
                     ('end_date', '>=', salary.date)], limit=1)
                for line in salary.tarja_cost_line:
                    num_reg = {
                        #'product_id': line.labor_id.product_id.id,
                        'name': 'Ref: ' + str(self.name),
                        'account_id': salary.company_id.step_journal_id.default_account_id.id,
                        'debit': round(line.trato_total, 4),
                        'credit': 0,
                        'analytic_distribution': {str(cost_temporada.cost_id.id)+ ","+
                                              str(line.cost_id.id)+ ","+
                                              str(line.labor_id.actividad_id.id) : 100},
                        'move_id': invoice_id.id,
                        'tax_ids': False
                    }
                    # vals.append(num_reg)
                    total = total + line.trato_total
                    line_asiento.append(num_reg)
                credit_num_reg = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': salary.company_id.step_journal_id.account_control_ids[0].id,
                    'debit': 0,
                    'credit': round(total, 4),
                    'move_id': invoice_id.id,
                    # 'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                    #                           str(line.cost_id.cost_id.id) + "," +
                    #                           str(line.labor_id.actividad_id.cost_id.id): 100},
                }
                line_asiento.append(credit_num_reg)
                create_line2 = self.env['account.move.line'].create(line_asiento)
            if salary.tarja_type == 'propio':
                line_asiento = []
                vals_analytic = {
                    'ref': self.name,
                    'date': self.date,
                    'journal_id': salary.company_id.propio_journal_id.id,
                    'move_type': 'entry',
                    'propio': True,
                }
                create_asiento = self.env['account.move'].create(vals_analytic)
                salary.invoice_id = create_asiento.id
                total_sueldo = 0.0
                total_seguro = 0.0
                total_feriado = 0.0
                total_ias = 0.0
                total = 0.0
                total_credito = 0.0
                total_debito = 0.0
                for line in salary.tarja_line:
                    total_sueldo += round(line.cost_sueldo, 4)
                    total_seguro += round(line.seguro, 4)
                    total_feriado += round(line.feriado, 4)
                    total_ias += round(line.ias, 4)
                cost_temporada = self.env['step.temporada'].search(
                    [('start_date', '<=', salary.date),
                     ('end_date', '>=', salary.date)])
                #Sueldos
                total = round(total_sueldo, 4) + round(total_feriado, 4) + round(total_ias, 4)
                total_debito += total
                account_sueldo = self.env['step.haber.costeo'].search(
                    [('type', '=', 'provi_sueldo'),
                     ('active', '=', True)], limit=1)
                credit_sueldo = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_sueldo.haber_account_id.id,
                    'debit': 0,
                    'credit': round(total_sueldo, 4),
                    'move_id': create_asiento.id,
                    # 'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                    #                           str(line.cost_id.cost_id.id) + "," +
                    #                           str(line.labor_id.actividad_id.cost_id.id): 100},
                }
                total_credito += round(total_sueldo, 4)
                line_asiento.append(credit_sueldo)
                # create_line1 = self.env['account.move.line'].create(credit_line)
                debit_sueldo = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_sueldo.debe_account_id.id,
                    'debit': round(total_sueldo, 4),
                    'credit': 0,
                    'move_id': create_asiento.id,
                    'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                                              str(line.cost_id.id) + "," +
                                              str(line.labor_id.actividad_id.id): 100},
                }
                line_asiento.append(debit_sueldo)
                #Seguro
                account_seguro = self.env['step.haber.costeo'].search(
                    [('type', '=', 'provi_seguro'),
                     ('active', '=', True)], limit=1)
                credit_seguro = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_seguro.haber_account_id.id,
                    'debit': 0,
                    'credit': round(total_seguro, 4),
                    'move_id': create_asiento.id,
                    # 'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                    #                           str(line.cost_id.cost_id.id) + "," +
                    #                           str(line.labor_id.actividad_id.cost_id.id): 100},
                }
                total_credito += round(total_seguro, 4)
                line_asiento.append(credit_seguro)
                # create_line1 = self.env['account.move.line'].create(credit_line)
                debit_seguro = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_seguro.debe_account_id.id,
                    'debit': round(total_seguro, 4),
                    'credit': 0,
                    'move_id': create_asiento.id,
                    'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                                              str(line.cost_id.id) + "," +
                                              str(line.labor_id.actividad_id.id): 100},
                }
                total_debito += round(total_seguro, 4)
                line_asiento.append(debit_seguro)
                #Feriado
                account_feriado = self.env['step.haber.costeo'].search(
                    [('type', '=', 'provi_feriado'),
                     ('active', '=', True)], limit=1)
                credit_feriado = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_feriado.haber_account_id.id,
                    'debit': 0,
                    'credit': round(total_feriado, 4),
                    'move_id': create_asiento.id,
                    # 'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                    #                           str(line.cost_id.cost_id.id) + "," +
                    #                           str(line.labor_id.actividad_id.cost_id.id): 100},
                }
                total_credito += round(total_feriado, 4)
                line_asiento.append(credit_feriado)
                debit_feriado = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_feriado.debe_account_id.id,
                    'debit': round(total_feriado, 4),
                    'credit': 0,
                    'move_id': create_asiento.id,
                    'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                                              str(line.cost_id.id) + "," +
                                              str(line.labor_id.actividad_id.id): 100},
                }
                total_debito += round(total_seguro, 4)
                line_asiento.append(debit_feriado)
                #IAS
                account_ias = self.env['step.haber.costeo'].search(
                    [('type', '=', 'provi_ias'),
                     ('active', '=', True)], limit=1)
                credit_ias = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_ias.haber_account_id.id,
                    'debit': 0,
                    'credit': round(total_ias, 4),
                    'move_id': create_asiento.id,
                    # 'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                    #                           str(line.cost_id.cost_id.id) + "," +
                    #                           str(line.labor_id.actividad_id.cost_id.id): 100},
                }
                total_credito += round(total_ias, 4)
                line_asiento.append(credit_ias)
                debit_ias = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_ias.debe_account_id.id,
                    'debit': round(total_ias, 4),
                    'credit': 0,
                    'move_id': create_asiento.id,
                    'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                                              str(line.cost_id.id) + "," +
                                              str(line.labor_id.actividad_id.id): 100},
                }
                total_debito += round(total_seguro, 4)
                line_asiento.append(debit_ias)

                create_line2 = self.env['account.move.line'].create(line_asiento)
                #self.target_invoice_id.with_context(target_invoice=True).action_post()
                #self.target_invoice_id.state = 'posted'

    def action_pag(self):
        for salary in self:
            salary.write({'state': 'pag'})

    def action_costeo(self):
        for salary in self:
            salary.write({'state': 'costo'})

    def action_to_costeo(self):
        for salary in self:
            salary.write({'state': 'auto'})

    @api.model
    def create(self, vals):
        if vals.get("tarja_type") == 'propio':
            vals["folio"] = str(self.env['ir.sequence'].next_by_code('registro_propia_seq'))
            salary_id = self.env['hr.salary.custom'].search(
                [('id', '=', vals["salary_id"])], limit=1).name
            vals["name"] = str(vals["folio"]) + '-' + str(salary_id)
        if vals.get("tarja_type") == 'contratista':
            vals["folio"] = str(self.env['ir.sequence'].next_by_code('registro_contratista_seq'))
            salary_contract_id = self.env['hr.salary.custom'].search(
                                            [('id', '=', vals["salary_id_contrac"])], limit=1).name
            partner_id = self.env['res.partner'].search(
                                            [('id', '=', vals["partner_id"])], limit=1).name
            vals["name"] = str(vals["folio"]) + '-' + str(salary_contract_id) + '-' + str(partner_id)
        return super(StepTarja, self).create(vals)

    def generate_report_per_worker(self):
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

        # Ancho de las columnas
        worksheet.set_column('A:AX', 15)

        # Data
        # inicio_mes = str(self.anio_select) + '-' + str(self.mes_select).zfill(2) + '-' + '01'
        # ultimo_de_mes = calendar.monthrange(int(self.anio_select), int(self.mes_select))
        # fin_mes = str(self.anio_select) + '-' + str(self.mes_select).zfill(2) + '-' + str(ultimo_de_mes[1])
        # result = self.env['account.move'].search(
        #     [('invoice_date', '>=', (inicio_mes)),
        #      ('invoice_date', '<=', (fin_mes)),
        #      ('move_type', '=', 'out_invoice')]
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
        # for factura in row:
        worksheet.write_string(row, 0, '1', numerico)
            # worksheet.write_string(row, 1, factura.company_id.name or '', caracteres)
            # worksheet.write_string(row, 2, str(self.anio_select) + str(self.mes_select), numerico)
            # worksheet.write_string(row, 3,
            #                        str(factura.company_id.vat).rstrip() + str(factura.l10n_latam_document_type_id.code).rstrip() + str(
            #                            factura.x_studio_serie_cliente).rstrip() + str(self.quitar_letras(factura.name)).rstrip().zfill(10),
            #                        caracteres)
            # worksheet.write_string(row, 4, str(factura.invoice_date) or '', numerico)
            # worksheet.write_string(row, 5, '', numerico)
            # worksheet.write_number(row, 6, int(factura.l10n_latam_document_type_id.code), numerico)
            # worksheet.write_string(row, 7, str(factura.x_studio_serie_cliente), caracteres)
            # worksheet.write_string(row, 8, str(self.quitar_letras(factura.name)).rstrip() or '', numerico)
            # worksheet.write_string(row, 9, '', caracteres) # Nro Final (Rango)
            # worksheet.write_string(row, 10, str(factura.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code) or 0, numerico)  # Tipo doc Identidad
            # worksheet.write_string(row, 11, str(factura.partner_id.vat) or '', numerico)  # Nro Doc Identidad
            # worksheet.write_string(row, 12, str(factura.partner_id.name) or '', caracteres)  # Apellidos Nombres / Razón Social
            # worksheet.write_number(row, 13, 0, numerico)  #
            # worksheet.write_number(row, 14, factura.amount_untaxed, numerico)  # Valor Facturado Exportación
            # worksheet.write_number(row, 15, 0, numerico)  # Dscto BI
            # worksheet.write_number(row, 16, factura.amount_tax, numerico)  # IGV/IPM
            # worksheet.write_number(row, 17, 0, numerico)  # Dscto IGV/IPM
            # worksheet.write_number(row, 18, 0, numerico)  #
            # worksheet.write_number(row, 19, 0, numerico)  #
            # worksheet.write_number(row, 20, 0, numerico)  #
            # worksheet.write_number(row, 21, 0, numerico)  #
            # worksheet.write_number(row, 22, 0, numerico)  #
            # worksheet.write_number(row, 23, 0, numerico)  #
            # worksheet.write_number(row, 24, 0, numerico)  #
            # worksheet.write_number(row, 25, factura.amount_total, numerico)  # Total CP
            # worksheet.write_string(row, 26, factura.currency_id.name, caracteres)  # Moneda
            # worksheet.write_number(row, 27, 1, numerico)  # Tipo Cambio
            # worksheet.write_string(row, 28, '', caracteres) # Fecha Emisión Doc Modificado
            # total += line[1]
        row += 1

        # Total
        # worksheet.write_string(row, 1, 'Total:', border)
        # worksheet.write_number(row, 2, total, border)
        # worksheet.write_formula(row, 3, f'SUM(C{first_row + 1}:C{row})', border)

        workbook.close()

        #
        # if not self.anio_select.isdigit():
        #     raise ValidationError(_("Ingresar valores correctos en los parametros."))
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
        # worksheet.write_string('B1:C1', 'ID', title_format)
        # worksheet.write_string('C1:C1', 'Periodo', title_format)
        # worksheet.write_string('D1:D1', 'CAR SUNAT', title_format)
        # worksheet.write_string('E1:E1', 'Fecha de Emisión', title_format)
        # worksheet.write_string('F1:F1', 'Fecha Vcto/Pago', title_format)
        # worksheet.write_string('G1:G1', 'Tipo CP/Doc', title_format)
        # worksheet.write_string('H1:H1', 'Serie del CDP', title_format)
        # worksheet.write_string('I1:I1', 'Nro CP o Doc Nro Inicial (Rango)', title_format)
        # worksheet.write_string('J1:J1', 'Nro Final (Rango)', title_format)
        # worksheet.write_string('K1:K1', 'Tipo Doc Identidad', title_format)
        # worksheet.write_string('L1:L1', 'Nro Doc Identidad', title_format)
        # worksheet.write_string('M1:M1', 'Apellidos Nombres / Razón Social', title_format)
        # worksheet.write_string('N1:N1', 'Valor Facturado Exportación', title_format)
        # worksheet.write_string('O1:O1', 'BI Gravada', title_format)
        # worksheet.write_string('P1:P1', 'Dscto BI', title_format)
        # worksheet.write_string('Q1:Q1', 'IGV/IPM', title_format)
        # worksheet.write_string('R1:R1', 'Dscto IGV/IPM', title_format)
        # worksheet.write_string('S1:S1', 'Mto Exonerado', title_format)
        # worksheet.write_string('T1:T1', 'Mto Inafecto', title_format)
        # worksheet.write_string('U1:U1', 'ISC', title_format)
        # worksheet.write_string('V1:V1', 'BI Grav IVAP', title_format)
        # worksheet.write_string('W1:W1', 'IVAP', title_format)
        # worksheet.write_string('X1:X1', 'ICBPER', title_format)
        # worksheet.write_string('Y1:Y1', 'Otros Tributos', title_format)
        # worksheet.write_string('Z1:Z1', 'Total CP', title_format)
        # worksheet.write_string('AA1:AA1', 'Moneda', title_format)
        # worksheet.write_string('AB1:AB1', 'Tipo Cambio', title_format)
        # worksheet.write_string('AC1:AC1', 'Fecha Emisión Doc Modificado', title_format)
        # worksheet.write_string('AD1:AD1', 'Tipo CP Modificado', title_format)
        # worksheet.write_string('AE1:AE1', 'Serie CP Modificado', title_format)
        # worksheet.write_string('AG1:AG1', 'ID Proyecto Operadores Atribución', title_format)
        # worksheet.write_string('AG1:AG1', 'ID Proyecto Operadores Atribución', title_format)
        # worksheet.write_string('AH1:AH1', 'CLU 1', title_format)
        # worksheet.write_string('AI1:AI1', 'CLU 2', title_format)
        # worksheet.write_string('AJ1:AJ1', 'CLU 3', title_format)
        # worksheet.write_string('AK1:AK1', 'CLU 4', title_format)
        # worksheet.write_string('AL1:AL1', 'CLU 5', title_format)
        # worksheet.write_string('AM1:AM1', 'CLU 6', title_format)
        # worksheet.write_string('AN1:AN1', 'CLU 7', title_format)
        # worksheet.write_string('AO1:AO1', 'CLU 8', title_format)
        # worksheet.write_string('AP1:AP1', 'CLU 9', title_format)
        # worksheet.write_string('AQ1:AQ1', 'CLU 10', title_format)
        # worksheet.write_string('AR1:AR1', 'CLU 11', title_format)
        # worksheet.write_string('AS1:AS1', 'CLU 12', title_format)
        # worksheet.write_string('AT1:AT1', 'CLU 13', title_format)
        # worksheet.write_string('AU1:AU1', 'CLU 14', title_format)
        # worksheet.write_string('AV1:AV1', 'CLU 15', title_format)
        # worksheet.write_string('AW1:AW1', 'CLU 16', title_format)
        # worksheet.write_string('AX1:AX1', 'CLU 17', title_format)

        # Ancho de las columnas
        worksheet.set_column('A:AX', 15)

        # # Data
        # inicio_mes = str(self.anio_select) + '-' + str(self.mes_select).zfill(2) + '-' + '01'
        # ultimo_de_mes = calendar.monthrange(int(self.anio_select), int(self.mes_select))
        # fin_mes = str(self.anio_select) + '-' + str(self.mes_select).zfill(2) + '-' + str(ultimo_de_mes[1])
        # result = self.env['account.move'].search(
        #     [('invoice_date', '>=', (inicio_mes)),
        #      ('invoice_date', '<=', (fin_mes)),
        #      ('move_type', '=', 'out_invoice')]
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
        # for factura in result:
        worksheet.write_string(row, 0, '1', numerico)
            # worksheet.write_string(row, 1, factura.company_id.name or '', caracteres)
            # worksheet.write_string(row, 2, str(self.anio_select) + str(self.mes_select), numerico)
            # worksheet.write_string(row, 3,
            #                        str(factura.company_id.vat).rstrip() + str
            #                            (factura.l10n_latam_document_type_id.code).rstrip() + str(
            #                            factura.x_studio_serie_cliente).rstrip() + str
            #                            (self.quitar_letras(factura.name)).rstrip().zfill(10),
            #                        caracteres)
            # worksheet.write_string(row, 4, str(factura.invoice_date) or '', numerico)
            # worksheet.write_string(row, 5, '', numerico)
            # worksheet.write_number(row, 6, int(factura.l10n_latam_document_type_id.code), numerico)
            # worksheet.write_string(row, 7, str(factura.x_studio_serie_cliente), caracteres)
            # worksheet.write_string(row, 8, str(self.quitar_letras(factura.name)).rstrip() or '', numerico)
            # worksheet.write_string(row, 9, '', caracteres) # Nro Final (Rango)
            # worksheet.write_string(row, 10, str(factura.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code) or 0, numerico)  # Tipo doc Identidad
            # worksheet.write_string(row, 11, str(factura.partner_id.vat) or '', numerico)  # Nro Doc Identidad
            # worksheet.write_string(row, 12, str(factura.partner_id.name) or '', caracteres)  # Apellidos Nombres / Razón Social
            # worksheet.write_number(row, 13, 0, numerico)  #
            # worksheet.write_number(row, 14, factura.amount_untaxed, numerico)  # Valor Facturado Exportación
            # worksheet.write_number(row, 15, 0, numerico)  # Dscto BI
            # worksheet.write_number(row, 16, factura.amount_tax, numerico)  # IGV/IPM
            # worksheet.write_number(row, 17, 0, numerico)  # Dscto IGV/IPM
            # worksheet.write_number(row, 18, 0, numerico)  #
            # worksheet.write_number(row, 19, 0, numerico)  #
            # worksheet.write_number(row, 20, 0, numerico)  #
            # worksheet.write_number(row, 21, 0, numerico)  #
            # worksheet.write_number(row, 22, 0, numerico)  #
            # worksheet.write_number(row, 23, 0, numerico)  #
            # worksheet.write_number(row, 24, 0, numerico)  #
            # worksheet.write_number(row, 25, factura.amount_total, numerico)  # Total CP
            # worksheet.write_string(row, 26, factura.currency_id.name, caracteres)  # Moneda
            # worksheet.write_number(row, 27, 1, numerico)  # Tipo Cambio
            # worksheet.write_string(row, 28, '', caracteres) # Fecha Emisión Doc Modificado
            # # total += line[1]
            # row += 1

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
            'name': 'Resultado_jamie',
            'type': 'ir.actions.act_window',
            'res_model': 'step_tarja', #self._name,
            'view_mode': 'form',
            'view_type': 'form',
            #'res_id': self.id,
            'target': 'new'
        }
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