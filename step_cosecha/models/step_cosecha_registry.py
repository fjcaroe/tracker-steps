# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from datetime import datetime, timedelta


class StepCosechaRegistry(models.Model):
    _name = 'step.cosecha.registry'
    _inherit = ['mail.thread']
    _description = 'Registro de Cosecha'
    _order = 'date desc, id desc'

    @api.model
    def default_get(self, fields):
        res = super(StepCosechaRegistry, self).default_get(fields)
        if self.env.context.get('step_default_contratista'):
            res.update({
                'type_tarea': 'contratista'
            })
        if self.env.context.get('step_default_propio'):
            res.update({
                'type_tarea': 'propio'
            })
        return res

    name = fields.Char(string='Nombre', index=True, required=True)
    type_tarea = fields.Selection(
        selection=[
            ('propio', 'Propio'),
            ('contratista', 'Contratista')
        ],
        string='Tipo Tareo',
        required=False,
        readonly=False,
        copy=False,
    )
    partner_id = fields.Many2one('res.partner', 'Contratista')
    salary_id = fields.Many2one(
        comodel_name='hr.salary.custom',
        string="Cuadrilla",
        required=False, ondelete='cascade')
    salary_id_contrac = fields.Many2one(
        comodel_name='hr.salary.custom',
        string="Cuadrilla Contratista",
        required=False, ondelete='cascade')
    tarja = fields.Char(string='No Tarja')
    date_tarja = fields.Datetime(string='Fecha', default=fields.Date.context_today, tracking=True)
    tarja_cajas = fields.Float("Cantidad Cj", required=False)
    tarja_kg = fields.Float("Cantidad Kg", required=False)
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    cuartel_id = fields.Many2one(
        comodel_name='step.cuartel.line',
        string="Cuartel",
        required=False, ondelete='cascade')
    variedad_id = fields.Many2one('step.variedad',
                                  string="Variedad",
                                  required=False, ondelete='cascade', copy=False)
    grupo_variedad_id_domain = fields.Many2many('step.grupo.variedad', related='pricelist_id.grupo_variedad_id_domain',
                                                string='Grupo Variedad')
    product_id = fields.Many2one('product.template', string='Producto', readonly=False)
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom", string="UdM", required=True
    )
    type_cosecha = fields.Selection(
        selection=[
            ('export', 'Exportación'),
            ('industrial', 'Industrial')
        ],
        string='Tipo Cosecha',
        required=False,
        readonly=False,
        copy=False,
    )
    packaging_ids = fields.Many2one('product.packaging',
                                     string='Tipo caja', copy=False)
    date = fields.Datetime(string='Fecha', default=fields.Date.context_today, tracking=True)
    folio = fields.Char(string='Folio', index=True)
    responsable_id = fields.Many2one('res.users', 'Responsable')
    super_id = fields.Many2one('hr.employee', 'Supervisor')
    fundo_id = fields.Many2one('step.fundo',
                               string="Fundo",
                               required=False, ondelete='cascade', copy=False)
    company_id = fields.Many2one('res.company', string='Empresa', required=False, default=lambda self: self.env.company)
    qty_pasada = fields.Integer(string='Pasada')
    cosecha_ubi_id = fields.Many2one('step.cosecha.ubicacion', 'Ubicación de operación')
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    registry_line = fields.One2many(
        comodel_name='step.cosecha.registry.line',
        inverse_name='registry_id',
        string="Movimientos Lines",
        copy=True, auto_join=True)
    registry_tarja_line = fields.One2many(
        comodel_name='step.cosecha.tarja.line',
        inverse_name='registry_id',
        string="Movimientos Tarja Lines",
        copy=True, auto_join=True)
    tarja_registry_line = fields.One2many(
        comodel_name='step.cosecha.tarja.registry.line',
        inverse_name='registry_id',
        string="Registros Tarja Lines",
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
    cost_id = fields.Many2one(
        'account.analytic.account', "Centro costos",
    )
    cost_id_domain = fields.Many2many('account.analytic.account', 'cosecha_cost_rel', 'cost_id',
                                      'cosecha_id', string='Centro costos')
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
    remunera = fields.Boolean(string='Remuneraciones')
    invoice_id = fields.Many2one('account.move', string='Contabilización')
    purchase_id = fields.Many2one('purchase.order', string='Orden de Compras')
    cos_recibida = fields.Boolean(string='Cosecha Recibida')

    @api.model
    def get_dashboard_data(self, days=30):
        """Entrega una lectura ejecutiva sin alterar el flujo transaccional."""
        days = max(7, min(int(days or 30), 365))
        date_from = fields.Datetime.now() - timedelta(days=days)
        period_domain = [('date', '>=', fields.Datetime.to_string(date_from))]

        totals = self.read_group(
            period_domain,
            ['tarja_kg:sum', 'tarja_cajas:sum'],
            [],
        )
        totals = totals[0] if totals else {}
        states = {
            key: self.search_count(period_domain + [('state', '=', key)])
            for key in ('in', 'apro', 'costo', 'cont')
        }
        types = {
            key: self.search_count(period_domain + [('type_tarea', '=', key)])
            for key in ('propio', 'contratista')
        }
        recent_records = self.search(period_domain, order='date desc, id desc', limit=8)

        return {
            'company_name': self.env.company.display_name,
            'days': days,
            'kpis': {
                'records': self.search_count(period_domain),
                'kilos': totals.get('tarja_kg', 0.0) or 0.0,
                'boxes': totals.get('tarja_cajas', 0.0) or 0.0,
                'received': self.search_count(period_domain + [('cos_recibida', '=', True)]),
                'pending_receipt': self.search_count(period_domain + [
                    ('type_tarea', '=', 'contratista'),
                    ('state', '=', 'cont'),
                    ('cos_recibida', '=', False),
                ]),
                'history': self.env['step.history.cosecha'].search_count([]),
            },
            'states': states,
            'types': types,
            'receptions': self.env['stock.picking'].search_count([('cosecha', '=', True)]),
            'locations': self.env['step.cosecha.ubicacion'].search_count([]),
            'processes': self.env['step.cosecha.proceso'].search_count([]),
            'recent': [{
                'id': record.id,
                'name': record.display_name,
                'date': fields.Datetime.to_string(record.date) if record.date else False,
                'type': record.type_tarea or False,
                'type_label': dict(record._fields['type_tarea'].selection).get(record.type_tarea, 'Sin tipo'),
                'state': record.state,
                'state_label': dict(record._fields['state'].selection).get(record.state, 'Sin estado'),
                'fundo': record.fundo_id.display_name or 'Sin fundo',
                'partner': record.partner_id.display_name or False,
                'kilos': record.tarja_kg or 0.0,
            } for record in recent_records],
        }

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
                if record.registry_line:
                    record.registry_line.unlink()
                if record.salary_id.salary_line:
                    for line in record.salary_id.salary_line:
                        vals.append((0, 0, {
                            'employee_id': line.employee_id.id,
                            'contract_id': self.env['hr.contract'].search(
                                [('employee_id', '=', line.employee_id.id)], limit=1).id,
                            # 'quantity': line.hours,
                        }))
                record.registry_line = vals

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
                if record.registry_tarja_line:
                    record.registry_tarja_line.unlink()
                if record.salary_id_contrac.contract_line:
                    for line in record.salary_id_contrac.contract_line:
                        vals.append((0, 0, {
                            'employee_id': line.employee_id.id,
                            # 'contract_id': line.contract_id.id,
                            # 'quantity': line.hours,
                        }))
                record.registry_tarja_line = vals

    def action_in(self):
        for cosecha in self:
            cosecha.write({'state': 'in'})

    def action_apro(self):
        for cosecha in self:
            cosecha.write({'state': 'apro'})

    def action_conta(self):
        for salary in self:
            salary.write({'state': 'cont'})
            if salary.type_tarea == 'contratista':
                salary.write({'state': 'cont'})
                line_asiento = []
                total = 0.0
                invoice_id = self.env['account.move'].create([{
                    'ref': salary.name,
                    'date': salary.date,
                    'move_type': 'entry',
                    'contra': True,
                    'state': 'draft',  # 'pro',
                    'partner_id': salary.partner_id.id,
                    'journal_id': salary.company_id.step_cosecha_journal_id.id,
                    'l10n_latam_document_type_id': salary.company_id.step_cosecha_document_type_id.id,
                }])
                salary.invoice_id = invoice_id.id
                vals = []
                cost_temporada = self.env['step.temporada'].search(
                    [('start_date', '<=', salary.date),
                     ('end_date', '>=', salary.date)], limit=1)
                for line in salary.registry_tarja_line:
                    # vals.append(num_reg)
                    total = total + line.trato_total
                num_reg = {
                    # 'product_id': line.labor_id.product_id.id,
                    'name': 'Ref: ' + str(self.name),
                    'account_id': salary.company_id.step_cosecha_journal_id.default_account_id.id,
                    'debit': round(total, 4),
                    'credit': 0,
                    'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                                              str(salary.cost_id.cost_id.id) + "," +
                                              str(salary.labor_id.actividad_id.cost_id.id): 100},
                    'move_id': invoice_id.id,
                    'tax_ids': False
                }
                line_asiento.append(num_reg)
                credit_num_reg = {
                    'name': 'Ref: ' + str(salary.name),
                    'account_id': salary.company_id.step_cosecha_journal_id.account_control_ids[0].id,
                    'debit': 0,
                    'credit': round(total, 4),
                    'move_id': invoice_id.id,
                    # 'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                    #                           str(line.cost_id.cost_id.id) + "," +
                    #                           str(line.labor_id.actividad_id.cost_id.id): 100},
                }
                line_asiento.append(credit_num_reg)
                create_line2 = self.env['account.move.line'].create(line_asiento)
            if salary.type_tarea == 'propio':
                line_asiento = []
                vals_analytic = {
                    'ref': self.name,
                    'date': self.date,
                    'journal_id': salary.company_id.step_cosecha_journal_id.id,
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
                for line in salary.registry_line:
                    total_sueldo += round(line.cost_sueldo, 4)
                    total_seguro += round(line.seguro, 4)
                    total_feriado += round(line.feriado, 4)
                    total_ias += round(line.ias, 4)
                cost_temporada = self.env['step.temporada'].search(
                    [('start_date', '<=', salary.date),
                     ('end_date', '>=', salary.date)])
                # Sueldos
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
                    'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                                              str(salary.cost_id.cost_id.id) + "," +
                                              str(salary.labor_id.actividad_id.cost_id.id): 100},
                }
                total_credito += round(total_sueldo, 4)
                line_asiento.append(credit_sueldo)
                # create_line1 = self.env['account.move.line'].create(credit_line)
                debit_sueldo = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_sueldo.debe_account_id.id,
                    'debit': round(total_sueldo, 4),
                    'credit': 0, #round(total, 4),
                    'move_id': create_asiento.id,
                    'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                                              str(salary.cost_id.cost_id.id) + "," +
                                              str(salary.labor_id.actividad_id.cost_id.id): 100},
                }
                line_asiento.append(debit_sueldo)
                # Seguro
                account_seguro = self.env['step.haber.costeo'].search(
                    [('type', '=', 'provi_seguro'),
                     ('active', '=', True)], limit=1)
                credit_seguro = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_seguro.haber_account_id.id,
                    'debit': 0,
                    'credit': round(total_seguro, 4),
                    'move_id': create_asiento.id,
                    'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                                              str(salary.cost_id.cost_id.id) + "," +
                                              str(salary.labor_id.actividad_id.cost_id.id): 100},
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
                                              str(salary.cost_id.cost_id.id) + "," +
                                              str(salary.labor_id.actividad_id.cost_id.id): 100},
                }
                total_debito += round(total_seguro, 4)
                line_asiento.append(debit_seguro)
                # Feriado
                account_feriado = self.env['step.haber.costeo'].search(
                    [('type', '=', 'provi_feriado'),
                     ('active', '=', True)], limit=1)
                credit_feriado = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_feriado.haber_account_id.id,
                    'debit': 0,
                    'credit': round(total_feriado, 4),
                    'move_id': create_asiento.id,
                    'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                                              str(salary.cost_id.cost_id.id) + "," +
                                              str(salary.labor_id.actividad_id.cost_id.id): 100},
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
                                              str(salary.cost_id.cost_id.id) + "," +
                                              str(salary.labor_id.actividad_id.cost_id.id): 100},
                }
                total_debito += round(total_seguro, 4)
                line_asiento.append(debit_feriado)
                # IAS
                account_ias = self.env['step.haber.costeo'].search(
                    [('type', '=', 'provi_ias'),
                     ('active', '=', True)], limit=1)
                credit_ias = {
                    'name': 'Ref: ' + str(self.name),
                    'account_id': account_ias.haber_account_id.id,
                    'debit': 0,
                    'credit': round(total_ias, 4),
                    'move_id': create_asiento.id,
                    'analytic_distribution': {str(cost_temporada.cost_id.id) + "," +
                                              str(salary.cost_id.cost_id.id) + "," +
                                              str(salary.labor_id.actividad_id.cost_id.id): 100},
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
                                              str(salary.cost_id.cost_id.id) + "," +
                                              str(salary.labor_id.actividad_id.cost_id.id): 100},
                }
                total_debito += round(total_seguro, 4)
                line_asiento.append(debit_ias)

                create_line2 = self.env['account.move.line'].create(line_asiento)
                # self.target_invoice_id.with_context(target_invoice=True).action_post()
                # self.target_invoice_id.state = 'posted'

    def action_pag(self):
        for cosecha in self:
            cosecha.write({'state': 'pag'})

    def action_costeo(self):
        for cosecha in self:
            cosecha.write({'state': 'costo'})

    def recibir_cosecha(self):
        for cosecha in self:
            if cosecha.type_tarea == 'contratista':
                total = 0
                for line in cosecha.registry_tarja_line:
                    total = total + line.quantity
                picking_id = self.env['stock.picking'].create([{
                    'partner_id': cosecha.partner_id.id,
                    'picking_type_id': self.env['stock.picking.type'].search(
                                [('code', '=', 'incoming')], limit=1).id,
                    'scheduled_date': cosecha.date,
                    'origin': cosecha.name,
                    'cosecha': True,
                }])
                picking_line = {
                    'name': cosecha.product_id.name,
                    'product_id': cosecha.product_id.id,
                    'product_uom_qty': total,
                    'product_uom': cosecha.product_uom_id.id,
                    'location_id': self.env['stock.location'].search(
                                [('name', '=', 'Vendors')], limit=1).id,
                    'location_dest_id': self.env['stock.location'].search(
                                [('name', '=', 'Stock')], limit=1).id,
                    'picking_id': picking_id.id,
                }
                create_line2 = self.env['stock.move'].create(picking_line)
                cosecha.write({'cos_recibida': True})

    @api.model
    def create(self, vals):
        if vals.get("type_tarea") == 'propio':
            seq = str(self.env['ir.sequence'].next_by_code('step_cosecha_pro_seq'))
            vals["name"] = seq + '-' + str(vals["name"])
        if vals.get("type_tarea") == 'contratista':
            seq = str(self.env['ir.sequence'].next_by_code('step_cosecha_contra_seq'))
            vals["name"] = seq + '-' + str(vals["name"])
        return super(StepCosechaRegistry, self).create(vals)
