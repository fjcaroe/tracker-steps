from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .control import CONSERVATION, OPERATING


class ContainerWorkOrder(models.Model):
    _name = 'step.harvest.container.work.order'
    _description = 'Orden de trabajo de envases'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(required=True, default='Nuevo', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Realizada')], default='draft',
                             required=True, readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date = fields.Date(required=True, default=fields.Date.context_today)
    operation = fields.Selection([('wash', 'Lavado'), ('sanitize', 'Sanitización'), ('repair', 'Reparación')],
                                 required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Bodega', required=True, check_company=True,
                                   domain="[('company_id', '=', company_id)]")
    warehouse_stock_id = fields.Many2one(related='warehouse_id.lot_stock_id')
    source_location_id = fields.Many2one('stock.location', string='Estado de origen', check_company=True,
                                        domain="[('location_id', '=', warehouse_stock_id), "
                                               "('step_container_operating', '!=', False)]")
    assigned_conservation = fields.Selection(CONSERVATION, string='Conservación del stock sin clasificar')
    assigned_operating = fields.Selection(OPERATING, string='Estado operativo del stock sin clasificar')
    product_id = fields.Many2one('product.product', string='Envase', required=True, check_company=True,
                                 domain="[('step_is_harvest_container','=',True),('is_storable','=',True)]")
    lot_id = fields.Many2one('stock.lot', string='Lote / serie', check_company=True,
                             domain="[('product_id','=',product_id)]")
    quantity = fields.Float(string='Envases procesados', required=True, digits='Product Unit of Measure')
    season_account_id = fields.Many2one('account.analytic.account', string='Temporada', required=True,
                                        check_company=True)
    center_account_id = fields.Many2one('account.analytic.account', string='Centro de costo', required=True,
                                        check_company=True)
    activity_account_id = fields.Many2one('account.analytic.account', string='Actividad', required=True,
                                          check_company=True)
    work_plan_id = fields.Many2one('account.analytic.plan', string='Plan de OT', required=True,
                                   default=lambda self: self.env['account.analytic.plan'].search(
                                       [('name', '=', 'OT Packing'), ('parent_id', '=', False)], limit=1))
    work_account_id = fields.Many2one('account.analytic.account', string='Cuenta de la OT', readonly=True,
                                      check_company=True, ondelete='restrict', copy=False)
    picking_id = fields.Many2one('stock.picking', string='Traslado de estados', readonly=True, check_company=True,
                                 ondelete='restrict', copy=False)
    consumption_ids = fields.One2many('stock.picking', 'step_container_work_order_id',
                                       string='Consumos desde inventario')
    inventory_cost = fields.Monetary(string='Insumos consumidos', compute='_compute_costs',
                                    groups='stock.group_stock_user,account.group_account_user')
    financial_cost = fields.Monetary(string='Servicios, personal y maquinaria', compute='_compute_costs',
                                     groups='stock.group_stock_user,account.group_account_user')
    total_cost = fields.Monetary(string='Costo total', compute='_compute_costs',
                                     groups='stock.group_stock_user,account.group_account_user')
    unit_cost = fields.Monetary(string='Costo por envase', compute='_compute_costs',
                                     groups='stock.group_stock_user,account.group_account_user')

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals, name=self.env['ir.sequence'].next_by_code('step.harvest.container.work.order'),
                          state='draft', work_account_id=False, picking_id=False) for vals in vals_list]
        records = super().create(vals_list)
        for record in records:
            # A fixed, company-scoped analytic account identifies this order across apps.
            account = self.env['account.analytic.account'].sudo().create({
                'name': record.name, 'plan_id': record.work_plan_id.id, 'company_id': record.company_id.id,
            })
            super(ContainerWorkOrder, record).write({'work_account_id': account.id})
        return records

    def write(self, vals):
        if {'state', 'picking_id', 'work_account_id', 'name', 'company_id', 'work_plan_id'} & vals.keys():
            raise UserError(_('Conserve la identidad y la trazabilidad de la orden.'))
        dimensions = {'season_account_id', 'center_account_id', 'activity_account_id'}
        if dimensions & vals.keys() and any(record._step_cost_lines() or record.consumption_ids for record in self):
            raise UserError(_('Conserve la imputación de las órdenes que ya tienen documentos asociados.'))
        if vals and any(record.state == 'done' for record in self):
            raise UserError(_('Una orden realizada no puede modificarse.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _step_keep_work_order(self):
        if self:
            raise UserError(_('Conserve la orden y su cuenta analítica para mantener la trazabilidad del costo.'))

    @api.constrains('season_account_id', 'center_account_id', 'activity_account_id', 'work_plan_id',
                    'quantity', 'product_id', 'lot_id')
    def _check_work_order(self):
        for order in self:
            plan = order.work_plan_id
            plans = (order.season_account_id | order.center_account_id | order.activity_account_id).root_plan_id
            if len(plans) != 3 or plan.parent_id or plan in plans:
                raise ValidationError(_('Temporada, centro, actividad y OT deben pertenecer a cuatro planes raíz distintos.'))
            if not order.product_id.is_storable or not order.product_id.step_is_harvest_container or order.quantity <= 0:
                raise ValidationError(_('Seleccione un envase almacenable y una cantidad positiva.'))
            if order.lot_id and order.lot_id.product_id != order.product_id:
                raise ValidationError(_('El lote debe pertenecer al envase seleccionado.'))

    def _step_cost_distribution(self):
        self.ensure_one()
        return {','.join(str(account.id) for account in [
            self.season_account_id, self.center_account_id, self.activity_account_id, self.work_account_id]): 100.0}

    def _step_cost_lines(self):
        self.ensure_one()
        lines = self.env['account.analytic.line'].sudo()
        if not self.work_account_id:
            return lines
        return lines.search([
            ('company_id', '=', self.company_id.id),
            (self.work_plan_id._column_name(), '=', self.work_account_id.id),
            ('move_line_id.parent_state', '=', 'posted'),
            ('move_line_id.account_id.account_type', 'in', ['expense', 'expense_direct_cost', 'expense_depreciation']),
            ('move_line_id.move_id.stock_move_id', '=', False),
        ])

    @api.depends('quantity', 'work_account_id', 'consumption_ids.state')
    def _compute_costs(self):
        for order in self:
            moves = order.sudo().consumption_ids.filtered(lambda p: p.state == 'done').move_ids.filtered(
                lambda move: move.state == 'done')
            returned = self.env['stock.move'].sudo().search([
                ('origin_returned_move_id', 'in', moves.ids), ('state', '=', 'done'),
            ]) if moves else moves
            inventory = -sum((moves | returned).stock_valuation_layer_ids.mapped('value'))
            finance = -sum(order._step_cost_lines().mapped('amount')) if order.work_account_id else 0.0
            order.inventory_cost = inventory
            order.financial_cost = finance
            order.total_cost = inventory + finance
            order.unit_cost = order.total_cost / order.quantity if order.quantity else 0.0

    def action_open_cost_lines(self):
        self.ensure_one()
        self.check_access('read')
        if not self.env.user.has_group('account.group_account_user'):
            raise UserError(_('Se requiere acceso a Contabilidad para ver los comprobantes.'))
        return {'type': 'ir.actions.act_window', 'name': _('Costos contabilizados'),
                'res_model': 'account.analytic.line', 'view_mode': 'list,form',
                'domain': [('id', 'in', self._step_cost_lines().ids)]}

    def action_complete(self):
        with self.env.cr.savepoint():
            for order in self.sorted('id'):
                order.check_access('write')
                self.env.cr.execute('SELECT id FROM step_harvest_container_work_order WHERE id = %s FOR UPDATE', [order.id])
                order.invalidate_recordset()
                if order.state != 'draft':
                    raise UserError(_('La orden ya está realizada.'))
                root = order.warehouse_stock_id
                source = order.source_location_id or root
                if order.source_location_id and source.location_id != root:
                    raise ValidationError(_('Seleccione un estado de la bodega de esta orden.'))
                if order.product_id.tracking != 'none' and not order.lot_id:
                    raise UserError(_('Indique el lote o serie de los envases procesados.'))
                conservation = source.step_container_conservation or order.assigned_conservation
                operating = source.step_container_operating or order.assigned_operating
                if not (conservation and operating):
                    raise UserError(_('Indique los estados del stock antes de realizar la operación.'))
                if order.operation == 'repair' and conservation == 'repairable':
                    conservation = 'good'
                elif order.operation == 'wash' and operating == 'dirty' and conservation == 'good':
                    operating = 'clean'
                elif order.operation == 'sanitize' and operating == 'clean' and conservation == 'good':
                    operating = 'sanitized'
                else:
                    raise UserError(_('Lavado requiere envases sucios en buen estado; sanitización requiere envases '
                                      'limpios en buen estado; reparación requiere envases reparables.'))
                dest = root._step_container_state_location(conservation, operating)
                picking = self.env['stock.picking']._step_move_containers(
                    order.warehouse_id, root, root,
                    [(order.product_id, order.quantity, order.lot_id, source, dest)], order.name, strict=True)
                super(ContainerWorkOrder, order).write({'picking_id': picking.id, 'state': 'done'})
        return True


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    step_container_work_order_id = fields.Many2one(
        'step.harvest.container.work.order', string='OT de envases (consumo)', copy=False,
        ondelete='restrict', check_company=True, index=True)

    def write(self, vals):
        if 'step_container_work_order_id' in vals and any(
                p.state == 'done' and p.step_container_work_order_id.id != vals['step_container_work_order_id']
                for p in self):
            raise UserError(_('Conserve la OT del consumo ya validado.'))
        return super().write(vals)

    def _action_done(self):
        for picking in self.filtered('step_container_work_order_id'):
            moves = picking.move_ids.filtered(lambda move: move.state not in ('done', 'cancel'))
            if any(move.location_id.usage != 'internal' or move.location_dest_id.usage not in ('inventory', 'production')
                   or move.product_id.step_is_harvest_container for move in moves):
                raise ValidationError(_('Impute a la OT solo consumos de insumos desde inventario, separados del traslado de envases.'))
        return super()._action_done()


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_account_move_vals(self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost):
        vals = super()._prepare_account_move_vals(
            credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost)
        order = (self.picking_id | self.origin_returned_move_id.picking_id).step_container_work_order_id
        if order:
            cost_account = credit_account_id if self.origin_returned_move_id else debit_account_id
            for command, _, line in vals.get('line_ids', []):
                if command == 0 and line.get('account_id') == cost_account:
                    line['analytic_distribution'] = order._step_cost_distribution()
        return vals


class Machinery(models.Model):
    _inherit = 'step.hrs.machinery'

    step_container_work_order_id = fields.Many2one(
        'step.harvest.container.work.order', string='OT de envases', copy=False, check_company=True,
        ondelete='restrict')

    @api.constrains('step_container_work_order_id', 'company_id')
    def _check_step_container_order(self):
        self._check_company(['step_container_work_order_id'])

    def write(self, vals):
        if 'step_container_work_order_id' in vals and any(
                row.invoice_id and row.step_container_work_order_id.id != vals['step_container_work_order_id']
                for row in self):
            raise UserError(_('El uso de maquinaria ya tiene un comprobante contable.'))
        return super().write(vals)

    def _debit_analytic_distribution(self, line):
        if self.step_container_work_order_id:
            return self.step_container_work_order_id._step_cost_distribution()
        return super()._debit_analytic_distribution(line)


class Labor(models.Model):
    _inherit = 'step.tarja'

    step_container_work_order_id = fields.Many2one(
        'step.harvest.container.work.order', string='OT de envases', copy=False, check_company=True,
        ondelete='restrict')

    @api.constrains('step_container_work_order_id', 'company_id')
    def _check_step_container_order(self):
        self._check_company(['step_container_work_order_id'])

    def write(self, vals):
        if 'step_container_work_order_id' in vals and any(
                row.invoice_id and row.step_container_work_order_id.id != vals['step_container_work_order_id']
                for row in self):
            raise UserError(_('La tarja ya tiene un comprobante contable.'))
        return super().write(vals)

    def action_conta(self):
        with self.env.cr.savepoint():
            result = super().action_conta()
            for row in self.filtered('step_container_work_order_id'):
                lines = row.invoice_id.line_ids.filtered(lambda line: line.debit > 0 and
                    line.account_id.account_type in ('expense', 'expense_direct_cost', 'expense_depreciation'))
                if not lines or row.invoice_id.state != 'draft':
                    raise UserError(_('La actividad debe generar un comprobante en borrador con cargos de gasto.'))
                lines.write({'analytic_distribution': row.step_container_work_order_id._step_cost_distribution()})
        return result



class AccountMove(models.Model):
    _inherit = 'account.move'

    step_container_work_order_id = fields.Many2one(
        'step.harvest.container.work.order', string='OT de envases', copy=False,
        check_company=True, ondelete='restrict')

    def write(self, vals):
        if 'step_container_work_order_id' in vals and any(
                move.state == 'posted' and move.step_container_work_order_id.id != vals['step_container_work_order_id']
                for move in self):
            raise UserError(_('No modifique la OT de un comprobante publicado.'))
        return super().write(vals)

    def _post(self, soft=True):
        for move in self.filtered('step_container_work_order_id'):
            if move.move_type not in ('in_invoice', 'in_refund', 'in_receipt', 'entry') or move.stock_move_id:
                raise ValidationError(_('Impute facturas de proveedor o comprobantes de gasto a la OT; '
                                        'los consumos se imputan desde Inventario.'))
            lines = move.line_ids.filtered(lambda line: line.account_id.account_type in (
                'expense', 'expense_direct_cost', 'expense_depreciation'))
            if not lines:
                raise ValidationError(_('El comprobante no tiene líneas de gastos para imputar a la OT.'))
            lines.write({'analytic_distribution': move.step_container_work_order_id._step_cost_distribution()})
        return super()._post(soft=soft)
