# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from odoo.exceptions import UserError
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
        required=True,
        readonly=False,
        copy=False,
    )
    partner_id = fields.Many2one('res.partner', 'Contratista')
    salary_id = fields.Many2one(
        comodel_name='hr.salary.custom',
        string="Cuadrilla",
        required=False, ondelete='restrict')
    salary_id_contrac = fields.Many2one(
        comodel_name='hr.salary.custom',
        string="Cuadrilla Contratista",
        required=False, ondelete='restrict')
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
        required=False, ondelete='restrict')
    variedad_id = fields.Many2one('step.variedad',
                                  string="Variedad",
                                  required=False, ondelete='restrict', copy=False)
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
                               required=False, ondelete='restrict', copy=False)
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company, index=True
    )
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
    invoice_id = fields.Many2one('account.move', string='Contabilización', copy=False)
    purchase_id = fields.Many2one('purchase.order', string='Orden de Compras', copy=False)
    cos_recibida = fields.Boolean(string='Cosecha Recibida', copy=False)
    total_kilos = fields.Float(
        string='Kilos reales', compute='_compute_production_totals', store=True,
        digits='Product Unit of Measure'
    )
    total_boxes = fields.Float(
        string='Cajas reales', compute='_compute_production_totals', store=True
    )
    reception_picking_id = fields.Many2one(
        'stock.picking', string='Recepción de bodega', readonly=True, copy=False
    )

    @api.depends(
        'tarja_kg', 'tarja_cajas', 'registry_tarja_line.quantity',
        'tarja_registry_line.qty_kg', 'tarja_registry_line.qty_caja'
    )
    def _compute_production_totals(self):
        for registry in self:
            line_kilos = sum(registry.registry_tarja_line.mapped('quantity'))
            tarja_kilos = sum(registry.tarja_registry_line.mapped('qty_kg'))
            tarja_boxes = sum(registry.tarja_registry_line.mapped('qty_caja'))
            registry.total_kilos = line_kilos or tarja_kilos or registry.tarja_kg
            registry.total_boxes = tarja_boxes or registry.tarja_cajas

    def _get_cosecha_costing_rule(self, rule_type):
        rule = self.env['step.haber.costeo'].search([
            ('type', '=', rule_type),
            ('active', '=', True),
        ], limit=1)
        if not rule or not rule.debe_account_id or not rule.haber_account_id:
            raise UserError(_(
                "Falta configurar las cuentas de debe y haber para '%s'.",
                rule_type,
            ))
        return rule

    def _get_cosecha_unit_price(self, labor, quantity, uom=False):
        self.ensure_one()
        if not self.pricelist_id or not labor:
            return self.env['product.pricelist.item'], 0.0
        price, rule_id = self.pricelist_id._get_product_price_rule(
            labor,
            float(quantity or 0.0),
            uom=uom or labor.uom_id,
            date=self.date or fields.Datetime.now(),
        )
        return self.env['product.pricelist.item'].browse(rule_id), price

    @api.model
    def get_dashboard_data(self, days=30):
        """Entrega una lectura ejecutiva sin alterar el flujo transaccional."""
        days = int(30 if days is None else days)
        if days == 0:
            period_domain = []
        else:
            days = max(7, min(days, 365))
            date_from = fields.Datetime.now() - timedelta(days=days)
            period_domain = [('date', '>=', fields.Datetime.to_string(date_from))]

        totals = self.read_group(
            period_domain,
            ['total_kilos:sum', 'total_boxes:sum'],
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
        reception_model = self.env['step.cosecha.recepcion']
        if days == 0:
            reception_domain = []
        else:
            reception_date_from = fields.Date.today() - timedelta(days=days)
            reception_domain = [('date', '>=', fields.Date.to_string(reception_date_from))]
        reception_totals = reception_model.read_group(
            reception_domain,
            ['total_kilos:sum', 'total_boxes:sum', 'observed_count:sum'],
            [],
        )
        reception_totals = reception_totals[0] if reception_totals else {}

        return {
            'company_name': self.env.company.display_name,
            'days': days,
            'period_label': 'Todo el histórico' if days == 0 else f'Últimos {days} días',
            'kpis': {
                'records': self.search_count(period_domain),
                'kilos': totals.get('total_kilos', 0.0) or 0.0,
                'boxes': totals.get('total_boxes', 0.0) or 0.0,
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
            'receptions': reception_model.search_count(reception_domain),
            'reception_in_progress': reception_model.search_count(reception_domain + [
                ('state', 'in', ('draft', 'progress')),
            ]),
            'reception_quality_alerts': reception_totals.get('observed_count', 0) or 0,
            'reception_kilos': reception_totals.get('total_kilos', 0.0) or 0.0,
            'warehouse_receptions': self.env['stock.picking'].search_count([('cosecha', '=', True)]),
            'locations': self.env['step.cosecha.ubicacion'].search_count([]),
            'processes': self.env['step.cosecha.proceso'].search_count(reception_domain),
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
                'kilos': record.total_kilos or 0.0,
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
                vals = [Command.clear()]
                if record.salary_id.salary_line:
                    for line in record.salary_id.salary_line:
                        vals.append(Command.create({
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
                vals = [Command.clear()]
                if record.salary_id_contrac.contract_line:
                    for line in record.salary_id_contrac.contract_line:
                        vals.append(Command.create({
                            'employee_id': line.employee_id.id,
                            # 'contract_id': line.contract_id.id,
                            # 'quantity': line.hours,
                        }))
                record.registry_tarja_line = vals

    def action_in(self):
        for cosecha in self:
            if cosecha.state != 'apro':
                raise UserError(_("Sólo un registro aprobado puede volver a Ingresado."))
            cosecha.write({'state': 'in'})

    def action_apro(self):
        for cosecha in self:
            if cosecha.state != 'in':
                raise UserError(_("Sólo un registro ingresado puede aprobarse."))
            cosecha.write({'state': 'apro'})

    def action_conta(self):
        for salary in self:
            if salary.state != 'costo':
                raise UserError(_(
                    "El registro %s debe estar en estado Costeo antes de contabilizar.",
                    salary.display_name,
                ))
            if salary.invoice_id:
                raise UserError(_(
                    "El registro %s ya tiene una contabilización asociada (%s).",
                    salary.display_name,
                    salary.invoice_id.display_name,
                ))
            journal = salary.company_id.step_cosecha_journal_id
            if not journal:
                raise UserError(_(
                    "Configure el diario de Cosecha para la empresa %s antes de contabilizar.",
                    salary.company_id.display_name,
                ))
            cost_temporada = self.env['step.temporada'].search([
                ('start_date', '<=', salary.date),
                ('end_date', '>=', salary.date),
            ], limit=1)
            if not cost_temporada or not cost_temporada.cost_id:
                raise UserError(_(
                    "No existe una temporada con centro de costo para la fecha del registro %s.",
                    salary.display_name,
                ))
            if not salary.cost_id or not salary.cost_id.cost_id:
                raise UserError(_(
                    "El centro de costo de %s no tiene la cuenta analítica requerida.",
                    salary.display_name,
                ))
            if (
                not salary.labor_id
                or not salary.labor_id.actividad_id
                or not salary.labor_id.actividad_id.cost_id
            ):
                raise UserError(_(
                    "La labor de %s debe tener actividad y cuenta analítica configuradas.",
                    salary.display_name,
                ))
            salary.write({'state': 'cont'})
            if salary.type_tarea == 'contratista':
                if not salary.partner_id:
                    raise UserError(_("Seleccione el contratista antes de contabilizar."))
                if not journal.default_account_id or not journal.account_control_ids:
                    raise UserError(_(
                        "El diario %s debe tener cuenta predeterminada y al menos una cuenta de control.",
                        journal.display_name,
                    ))
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
                    'journal_id': journal.id,
                    'l10n_latam_document_type_id': salary.company_id.step_cosecha_document_type_id.id,
                }])
                salary.invoice_id = invoice_id.id
                vals = []
                for line in salary.registry_tarja_line:
                    # vals.append(num_reg)
                    total = total + line.trato_total
                num_reg = {
                    # 'product_id': line.labor_id.product_id.id,
                    'name': 'Ref: ' + str(salary.name),
                    'account_id': journal.default_account_id.id,
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
                    'account_id': journal.account_control_ids[0].id,
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
                    'ref': salary.name,
                    'date': salary.date,
                    'journal_id': journal.id,
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
                # Sueldos
                total = round(total_sueldo, 4) + round(total_feriado, 4) + round(total_ias, 4)
                total_debito += total
                account_sueldo = self._get_cosecha_costing_rule('provi_sueldo')
                credit_sueldo = {
                    'name': 'Ref: ' + str(salary.name),
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
                    'name': 'Ref: ' + str(salary.name),
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
                account_seguro = self._get_cosecha_costing_rule('provi_seguro')
                credit_seguro = {
                    'name': 'Ref: ' + str(salary.name),
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
                    'name': 'Ref: ' + str(salary.name),
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
                account_feriado = self._get_cosecha_costing_rule('provi_feriado')
                credit_feriado = {
                    'name': 'Ref: ' + str(salary.name),
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
                    'name': 'Ref: ' + str(salary.name),
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
                account_ias = self._get_cosecha_costing_rule('provi_ias')
                credit_ias = {
                    'name': 'Ref: ' + str(salary.name),
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
                    'name': 'Ref: ' + str(salary.name),
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

    def action_costeo(self):
        for cosecha in self:
            if cosecha.state != 'apro':
                raise UserError(_("Sólo un registro aprobado puede pasar a Costeo."))
            cosecha.write({'state': 'costo'})

    def recibir_cosecha(self, reception_id=False):
        for cosecha in self:
            if cosecha.type_tarea != 'contratista':
                raise UserError(_("La recepción de bodega sólo aplica a cosecha contratista."))
            if cosecha.cos_recibida or cosecha.reception_picking_id:
                raise UserError(_("La recepción de bodega de %s ya fue generada.", cosecha.display_name))
            reception = self.env['step.cosecha.recepcion'].browse(reception_id).exists()
            if reception and reception.registry_id != cosecha:
                raise UserError(_("El control de recepción no corresponde a este registro de cosecha."))
            if not cosecha.partner_id:
                raise UserError(_("Seleccione el contratista antes de generar la recepción."))
            if not reception and (not cosecha.product_id or not cosecha.product_uom_id):
                raise UserError(_(
                    "Complete producto y unidad de medida antes de generar la recepción."
                ))

            existing_picking = self.env['stock.picking'].search([
                ('origin', '=', cosecha.name),
                ('cosecha', '=', True),
                ('state', '!=', 'cancel'),
                ('company_id', '=', cosecha.company_id.id),
            ], limit=1)
            if existing_picking:
                raise UserError(_(
                    "Ya existe la recepción %s para este registro.",
                    existing_picking.display_name,
                ))

            picking_type = self.env['stock.picking.type'].with_company(cosecha.company_id).search([
                ('code', '=', 'incoming'),
                ('company_id', 'in', [False, cosecha.company_id.id]),
            ], order='company_id desc, sequence, id', limit=1)
            if not picking_type:
                raise UserError(_(
                    "No existe un tipo de operación de recepción para la empresa %s.",
                    cosecha.company_id.display_name,
                ))
            source_location = (
                picking_type.default_location_src_id
                or self.env.ref('stock.stock_location_suppliers', raise_if_not_found=False)
            )
            destination_location = (
                picking_type.default_location_dest_id
                or picking_type.warehouse_id.lot_stock_id
            )
            if not source_location or not destination_location:
                raise UserError(_(
                    "Configure las ubicaciones de origen y destino en %s.",
                    picking_type.display_name,
                ))

            move_commands = []
            if reception:
                if not reception.recep_line:
                    raise UserError(_("Agregue al menos una línea al control de recepción."))
                for line in reception.recep_line:
                    product_variant = line.product_id.product_variant_ids[:1]
                    uom = line.uom_id or product_variant.uom_id
                    if not line.product_id or not product_variant or not uom:
                        raise UserError(_(
                            "Todas las líneas de recepción deben tener producto y unidad de medida."
                        ))
                    if line.quantity <= 0:
                        raise UserError(_(
                            "La cantidad recibida de %s debe ser mayor que cero.",
                            line.product_id.display_name,
                        ))
                    move_commands.append(Command.create({
                        'name': line.product_id.display_name,
                        'product_id': product_variant.id,
                        'product_uom_qty': line.quantity,
                        'product_uom': uom.id,
                        'location_id': source_location.id,
                        'location_dest_id': destination_location.id,
                    }))
            else:
                product_variant = cosecha.product_id.product_variant_ids[:1]
                if not product_variant:
                    raise UserError(_("El producto seleccionado no tiene una variante utilizable en inventario."))
                total = cosecha.total_kilos
                if total <= 0:
                    raise UserError(_("Ingrese una cantidad mayor que cero antes de generar la recepción."))
                move_commands.append(Command.create({
                    'name': cosecha.product_id.display_name,
                    'product_id': product_variant.id,
                    'product_uom_qty': total,
                    'product_uom': cosecha.product_uom_id.id,
                    'location_id': source_location.id,
                    'location_dest_id': destination_location.id,
                }))

            picking = self.env['stock.picking'].create({
                'partner_id': cosecha.partner_id.id,
                'picking_type_id': picking_type.id,
                'scheduled_date': cosecha.date,
                'origin': cosecha.name,
                'company_id': cosecha.company_id.id,
                'location_id': source_location.id,
                'location_dest_id': destination_location.id,
                'cosecha': True,
                'harvest_registry_id': cosecha.id,
                'move_ids_without_package': move_commands,
            })
            cosecha.write({
                'cos_recibida': False,
                'reception_picking_id': picking.id,
            })

        if len(self) == 1 and self.reception_picking_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Recepción de bodega'),
                'res_model': 'stock.picking',
                'res_id': self.reception_picking_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return True

    def unlink(self):
        protected = self.filtered(
            lambda record: record.state == 'cont'
            or record.invoice_id
            or record.reception_picking_id
        )
        if protected:
            raise UserError(_(
                "No puede eliminar registros contabilizados o con recepción de bodega: %s",
                ', '.join(protected.mapped('display_name')),
            ))
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            task_type = vals.get('type_tarea')
            if task_type == 'propio':
                seq = self.env['ir.sequence'].next_by_code('step_cosecha_pro_seq') or _('Nuevo')
                vals['name'] = f"{seq}-{vals.get('name') or _('Cosecha')}"
            elif task_type == 'contratista':
                seq = self.env['ir.sequence'].next_by_code('step_cosecha_contra_seq') or _('Nuevo')
                vals['name'] = f"{seq}-{vals.get('name') or _('Cosecha')}"
        return super().create(vals_list)
