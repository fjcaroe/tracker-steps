# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepMoviRegistry(models.Model):
    _name = 'step.movi.registry'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=False)
    date = fields.Datetime(string='Fecha')
    fundo_id = fields.Many2one('step.fundo',
                               string="Fundo",
                               required=False, ondelete='cascade', copy=False)
    recorrido_id = fields.Many2one('hr.route', 'Recorrido', required=False)
    vehicle_id = fields.Many2one('fleet.vehicle', 'Vehículo', required=False)
    responsable_id = fields.Many2one('res.users', 'Responsable')
    partner_id = fields.Many2one('res.partner', 'Transportista')
    chofer_id = fields.Many2one('res.partner', 'Chofer')
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Lista de tarifa'
    )
    company_id = fields.Many2one('res.company', string='Empresa', required=False, default=lambda self: self.env.company)
    note = fields.Html(string="Notas")
    movi_line = fields.One2many(
        comodel_name='step.movi.registry.line',
        inverse_name='movi_id',
        string="Movimientos Lines",
        copy=True, auto_join=True)
    movi_cost_line = fields.One2many(
        comodel_name='step.movi.cost.line',
        inverse_name='movi_id',
        string="Movimientos costos Lines",
        copy=True, auto_join=True)
    movi_cont_line = fields.One2many(
        comodel_name='step.movi.cont.line',
        inverse_name='movi_id',
        string="Movimientos contable Lines",
        copy=True, auto_join=True)
    state = fields.Selection(
        selection=[
            ('in', 'Ingresado'),
            ('apro', 'Aprobado'),
            ('costo', 'Costeo'),
            ('cont', 'Contabilizado')
        ],
        string='Estado',
        required=True,
        readonly=False,
        copy=False,
        default='in',
    )
    purchase_id = fields.Many2one('purchase.order', string='Orden de Compras')
    invoice_id = fields.Many2one('account.move', string='Contabilización')

    def action_costeo(self):
        self.ensure_one()
        total_div = 0
        for record in self:
            if record.movi_line:
                vals = []
                tarifa = 0
                if record.pricelist_id:
                    for item in record.pricelist_id.move_item:
                        if record.recorrido_id == item.recorrido_id:
                            tarifa = item
                # if record.movi_cost_line:
                #     record.movi_cost_line.unlink()
                # if record.movi_cont_line:
                #     record.movi_cont_line.unlink()
                jamie = record.date.date()
                employees = []
                costos = []
                tarja = self.env['step.tarja'].search(
                    [('fundo_id', '=', record.fundo_id.id),
                     ('date', '=', record.date.date()),
                     ('company_id', '=', record.company_id.id),
                     ('tarja_type', '=', 'propio')])

                print('Encontro: ' + str(tarja))
                for tar in tarja:
                    for emp in tar.tarja_line:
                        if emp.employee_id.id not in employees:
                            employees.append(emp.employee_id.id)
                            total_div = total_div + 1
                            costos.append({
                                'employee_id': emp.employee_id.id,
                                'cost_id': emp.cost_id.id,
                                'labor_id': emp.labor_id.id,
                                'parte': 1,
                            })
                        else:
                            for a in costos:
                                if a['employee_id'] == emp.employee_id.id:
                                    a['parte'] = a['parte'] + 1
                for line in record.movi_line:
                    if line.employee_id.id in employees:
                        cost_id = ''
                        labor_id = ''
                        parte = 0
                        for a in costos:
                            if a['employee_id'] == line.employee_id.id:
                                cost_id = a['cost_id']
                                labor_id = a['labor_id']
                                parte = a['parte']
                            # jamie = (a['cost_id'] for a in costos if a['employee_id'] == line.employee_id.id)
                        if line.operacion == 'in':
                            tarifa_in = 0
                            if tarifa.cobro_type in ['ida','ida_vuelta']:
                                tarifa_in = tarifa.tarifa
                            vals.append((0, 0, {
                                'employee_id': line.employee_id.id,
                                'recorrido_ent': record.recorrido_id.desde,
                                'cost_in': float(tarifa_in) / int(len(record.movi_line)), # total_div int(len(record.movi_line)),
                                'cost_total': float(tarifa_in) / int(len(record.movi_line)), #int(len(record.movi_line)),
                                'cost_id': cost_id,
                                'labor_id': labor_id,
                            }))
                        if line.operacion == 'out':
                            tarifa_out = 0
                            if tarifa.cobro_type in ['vuelta', 'ida_vuelta']:
                                tarifa_out = tarifa.tarifa
                            vals.append((0, 0, {
                                'employee_id': line.employee_id.id,
                                'recorrido_sal': record.recorrido_id.hasta,
                                'cost_out': float(tarifa_out) / int(len(record.movi_line)), #int(len(record.movi_line)),
                                'cost_total': float(tarifa_out) / int(len(record.movi_line)), #int(len(record.movi_line)),
                            }))

                record.movi_cost_line = vals
                record.write({'state': 'costo'})

    def action_in(self):
        for cosecha in self:
            cosecha.write({'state': 'in'})

    def action_apro(self):
        for cosecha in self:
            cosecha.write({'state': 'apro'})

    def action_conta(self):
        for movi in self:
            movi.write({'state': 'cont'})
            line_asiento = []
            total = 0.0
            invoice_id = self.env['account.move'].create([{
                'ref': self.name,
                'date': self.date,
                'move_type': 'entry',
                'moviliza': True,
                'state': 'draft',  # 'pro',
                'partner_id': movi.partner_id.id,
                'journal_id': movi.company_id.step_movi_journal_id.id,
                'l10n_latam_document_type_id': movi.company_id.step_movi_document_type_id.id,
            }])
            movi.invoice_id = invoice_id.id
            vals = []
            cost_temporada = self.env['step.temporada'].search(
                [('start_date', '<=', movi.date),
                 ('end_date', '>=', movi.date)], limit=1)
            for line in movi.movi_cost_line:
                num_reg = {
                    # 'product_id': line.labor_id.product_id.id,
                    'name': 'Ref: ' + str(self.name),
                    'account_id': movi.company_id.step_movi_journal_id.default_account_id.id,
                    'debit': round(line.cost_total, 4),
                    'credit': 0,
                    'analytic_distribution': {str(cost_temporada.cost_id.id)+ ","+
                                              str(line.cost_id.id)+ ","+
                                              str(line.labor_id.actividad_id.id) : 100},
                    'move_id': invoice_id.id,
                    'tax_ids': False
                }
                # vals.append(num_reg)
                total = total + line.cost_total
                line_asiento.append(num_reg)
            credit_num_reg = {
                'name': 'Ref: ' + str(self.name),
                'account_id': movi.company_id.step_movi_journal_id.account_control_ids[0].id,
                'debit': 0,
                'credit': round(total, 4),
                'move_id': invoice_id.id,
                # 'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                #                           str(line.cost_id.cost_id.id) + "," +
                #                           str(line.labor_id.actividad_id.cost_id.id): 100},
            }
            line_asiento.append(credit_num_reg)
            create_line2 = self.env['account.move.line'].create(line_asiento)



            # purchase_id = self.env['purchase.order'].create([{
            #     'partner_id': movi.partner_id.id,
            # }])
            # movi.purchase_id = purchase_id.id
            # vals = []
            # cost_temporada = self.env['step.temporada'].search(
            #     [('start_date', '<=', movi.date),
            #      ('end_date', '>=', movi.date)], limit=1)
            # for line in movi.movi_cost_line:
            #     # producto = self.env['product.product'].search(
            #     # [('product_tmpl_id', '<=', line.labor_id.product_id.id)], limit=1)
            #     num_reg = {
            #         'name': movi.company_id.movi_product_id.name,
            #         'product_id': movi.company_id.movi_product_id.id,
            #         'analytic_distribution': {str(cost_temporada.cost_id.id)+ ","+
            #                                   str(line.cost_id.cost_id.id)+ ","+
            #                                   str(line.labor_id.product_id.actividad_id.cost_id.id) : 100},
            #         'product_qty': 1,
            #         # 'product_uom': line.uom_id.id,
            #         'price_unit': line.cost_total,
            #         'order_id': purchase_id.id,
            #         'taxes_id': False
            #     }
            #     # vals.append(num_reg)
            #     order_line = self.env['purchase.order.line'].create(num_reg)
            #     purchase_id.button_confirm()

    def action_pag(self):
        for cosecha in self:
            cosecha.write({'state': 'pag'})

    def action_to_costeo(self):
        for record in self:
            if record.movi_cost_line:
                record.movi_cost_line.unlink()
            record.write({'state': 'apro'})

    # def action_costeo(self):
    #     for cosecha in self:
    #         cosecha.write({'state': 'costo'})

    @api.model
    def create(self, vals):
        vals["name"] = str(self.env['ir.sequence'].next_by_code('step_moviliza_seq'))
        return super(StepMoviRegistry, self).create(vals)