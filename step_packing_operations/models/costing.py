"""Reviewed OT costs and native landed costs on company-owned export output."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

from .process_control import _INTERNAL

_COST = object()


class PackingCompany(models.Model):
    _inherit = 'res.company'
    step_packing_material_cost_service_id = fields.Many2one('product.product', string='Servicio costo de embalajes')
    step_packing_material_cost_account_id = fields.Many2one('account.account', string='Cuenta consumo de embalajes')


class PackingCost(models.Model):
    _name = 'step.packing.cost'
    _description = 'Costo de OT de Packing'
    _check_company_auto = True

    production_id = fields.Many2one('step.packing.production', required=True, ondelete='restrict', check_company=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    name = fields.Char('Concepto', required=True)
    product_id = fields.Many2one('product.product', string='Servicio de costo', required=True)
    amount = fields.Monetary('Costo de la OT', required=True)
    credit_account_id = fields.Many2one('account.account', string='Cuenta de contrapartida', required=True,
        help='Cuenta donde se reconoció el costo. La capitalización reclasifica este importe; no crea una factura.')
    source_line_id = fields.Many2one('account.move.line', string='Gasto contable publicado', check_company=True)
    source_reference = fields.Char('Respaldo / referencia')
    material_move_id = fields.Many2one('stock.move', readonly=True, copy=False)
    allocation_id = fields.Many2one('step.packing.cost.allocation', readonly=True, ondelete='restrict')
    export_percent = fields.Float('% capitalizable a fruta E', required=True,
        help='El resto permanece como costo del proceso y no se agrega al inventario de terceros.')
    capitalizable_amount = fields.Monetary(compute='_compute_capitalizable')

    @api.depends('amount', 'export_percent')
    def _compute_capitalizable(self):
        for row in self:
            row.capitalizable_amount = row.currency_id.round(row.amount * row.export_percent / 100)

    def _check_editable(self):
        self.production_id._lock_process()
        if any(row.production_id.state != 'closed' for row in self):
            raise UserError(_('Los costos se editan después del cierre y antes de aprobar el costeo.'))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env['step.packing.production'].browse([row['production_id'] for row in vals_list])
        parents._lock_process()
        if any(row.state != 'closed' for row in parents):
            raise UserError(_('Cierre la OT antes de registrar sus costos.'))
        if self.env.context.get('_packing_cost') is not _COST and any(row.get('material_move_id') or row.get('allocation_id') for row in vals_list):
            raise UserError(_('Los consumos y asignaciones se generan desde sus acciones.'))
        return super().create(vals_list)

    def write(self, vals):
        self._check_editable()
        if {'production_id', 'material_move_id', 'allocation_id'} & vals.keys() or any(row.allocation_id or row.material_move_id for row in self):
            raise UserError(_('La asignación y el consumo nativo conservan su origen e importe.'))
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        if any(row.material_move_id or row.allocation_id and self.env.context.get('_packing_cost') is not _COST for row in self):
            raise UserError(_('No se elimina un costo originado por consumo o asignación.'))
        return super().unlink()

    @api.constrains('amount', 'export_percent', 'credit_account_id', 'source_line_id', 'product_id')
    def _check_values(self):
        for row in self:
            if row.amount <= 0 or not 0 <= row.export_percent <= 100:
                raise ValidationError(_('Indique un costo positivo y un porcentaje entre 0 y 100.'))
            if row.company_id not in row.credit_account_id.company_ids or row.credit_account_id.account_type in ('asset_receivable', 'liability_payable'):
                raise ValidationError(_('La contrapartida debe ser una cuenta de esta empresa, distinta de clientes/proveedores.'))
            if row.product_id.type != 'service':
                raise ValidationError(_('Use un producto de tipo servicio para el concepto de costo.'))
            if row.source_line_id:
                source = row.source_line_id
                if source.move_id.state != 'posted' or source.company_id != row.company_id or source.balance <= 0 or source.account_id != row.credit_account_id:
                    raise ValidationError(_('Seleccione un gasto publicado, deudor y con la misma cuenta de contrapartida.'))


class PackingCostAllocation(models.Model):
    _name = 'step.packing.cost.allocation'
    _description = 'Asignación de costo compartido a OT'
    _inherit = ['mail.thread']
    _check_company_auto = True

    name = fields.Char('Concepto', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    production_ids = fields.Many2many('step.packing.production', string='OT cerradas', check_company=True)
    amount = fields.Monetary('Costo a distribuir', required=True)
    basis = fields.Selection([('kg', 'Kilos ingresados'), ('hours', 'Horas efectivas'), ('labor', 'Horas-persona')], required=True, default='kg')
    product_id = fields.Many2one('product.product', string='Servicio de costo', required=True)
    credit_account_id = fields.Many2one('account.account', string='Contrapartida', required=True)
    source_line_id = fields.Many2one('account.move.line', string='Gasto publicado', check_company=True)
    source_reference = fields.Char('Respaldo / referencia', required=True)
    state = fields.Selection([('draft', 'Borrador'), ('allocated', 'Asignado')], required=True, default='draft', readonly=True, copy=False)
    cost_ids = fields.One2many('step.packing.cost', 'allocation_id', readonly=True)

    def action_allocate(self):
        self.check_access('write')
        with self.env.cr.savepoint():
            for row in self:
                self.env.cr.execute('SELECT id FROM step_packing_cost_allocation WHERE id=%s FOR UPDATE', [row.id])
                row.invalidate_recordset()
                if row.state == 'allocated':
                    continue
                productions = row.production_ids.sorted('id')
                productions._lock_process()
                if not productions or any(ot.state != 'closed' or ot.company_id != row.company_id for ot in productions) or row.amount <= 0:
                    raise UserError(_('Seleccione OT cerradas de esta empresa y un costo positivo.'))
                weights = [(ot, ot.step_packing_input_kg if row.basis == 'kg' else ot.effective_hours * (ot.workers if row.basis == 'labor' else 1)) for ot in productions]
                if any(weight <= 0 for _, weight in weights):
                    raise UserError(_('Todas las OT deben tener una base de distribución positiva. Revise kilos, horas y dotación.'))
                total = sum(weight for _, weight in weights)
                remaining = row.currency_id.round(row.amount)
                for index, (ot, weight) in enumerate(weights):
                    amount = remaining if index == len(weights) - 1 else row.currency_id.round(row.amount * weight / total)
                    remaining -= amount
                    if amount:
                        self.env['step.packing.cost'].with_context(_packing_cost=_COST).create({
                            'production_id': ot.id, 'allocation_id': row.id, 'name': row.name,
                            'product_id': row.product_id.id, 'amount': amount, 'credit_account_id': row.credit_account_id.id,
                            'source_line_id': row.source_line_id.id, 'source_reference': row.source_reference,
                            'export_percent': ot._export_cost_percent(),
                        })
                productions._check_cost_sources()
                row.with_context(_packing_cost=_COST).write({'state': 'allocated'})
        return True

    def action_reopen(self):
        self.check_access('write')
        for row in self:
            self.env.cr.execute('SELECT id FROM step_packing_cost_allocation WHERE id=%s FOR UPDATE', [row.id])
            row.invalidate_recordset()
            row.production_ids._lock_process()
            if row.state != 'allocated' or any(ot.state != 'closed' for ot in row.production_ids):
                raise UserError(_('Reabra solo asignaciones cuyas OT aún no tienen costeo aprobado.'))
            row.cost_ids.with_context(_packing_cost=_COST).unlink()
            row.with_context(_packing_cost=_COST).write({'state': 'draft'})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if any(row.get('state', 'draft') != 'draft' or row.get('cost_ids') for row in vals_list):
            raise UserError(_('La asignación se crea en borrador.'))
        return super().create(vals_list)

    def write(self, vals):
        self.check_access('write')
        if self:
            self.env.cr.execute('SELECT id FROM step_packing_cost_allocation WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset()
        if 'state' in vals and self.env.context.get('_packing_cost') is not _COST or 'cost_ids' in vals:
            raise UserError(_('Use la acción de asignación.'))
        if any(row.state != 'draft' for row in self) and not (self.env.context.get('_packing_cost') is _COST and vals == {'state': 'draft'}):
            raise UserError(_('Una asignación aplicada conserva sus importes y bases.'))
        return super().write(vals)

    def unlink(self):
        if any(row.state != 'draft' for row in self):
            raise UserError(_('No se elimina una asignación aplicada.'))
        return super().unlink()


class PackingProduction(models.Model):
    _inherit = 'step.packing.production'

    currency_id = fields.Many2one(related='company_id.currency_id')
    cost_ids = fields.One2many('step.packing.cost', 'production_id', string='Costos de transformación')
    transformation_cost = fields.Monetary(compute='_compute_costs', string='Costo de transformación')
    capitalizable_cost = fields.Monetary(compute='_compute_costs', string='Costo a capitalizar')
    fruit_stock_cost = fields.Monetary(compute='_compute_costs', string='Valor inicial fruta E')
    total_process_cost = fields.Monetary(compute='_compute_costs', string='Costo total OT')
    cost_per_export_kg = fields.Monetary(compute='_compute_costs', string='Costo por kg E')
    default_export_cost_percent = fields.Float(compute='_compute_costs')
    cost_approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    cost_approved_at = fields.Datetime(readonly=True, copy=False)
    landed_cost_id = fields.Many2one('stock.landed.cost', string='Capitalización nativa', readonly=True, copy=False, check_company=True)

    @api.depends('cost_ids.amount', 'cost_ids.export_percent', 'output_picking_id.move_ids.stock_valuation_layer_ids.value', 'step_packing_export_kg')
    def _compute_costs(self):
        for ot in self:
            ot.transformation_cost = sum(ot.cost_ids.mapped('amount'))
            ot.capitalizable_cost = sum(ot.cost_ids.mapped('capitalizable_amount'))
            original = ot._export_cost_moves().stock_valuation_layer_ids.filtered(lambda layer: not layer.stock_landed_cost_id)
            ot.fruit_stock_cost = sum(original.mapped('value'))
            ot.total_process_cost = ot.fruit_stock_cost + ot.transformation_cost
            ot.cost_per_export_kg = ((ot.fruit_stock_cost + ot.capitalizable_cost) / ot.step_packing_export_kg if ot.step_packing_export_kg else 0)
            ot.default_export_cost_percent = ot._export_cost_percent()

    def action_import_material_costs(self):
        self._lock_process()
        for ot in self:
            if ot.state != 'closed':
                raise UserError(_('Importe los consumos en una OT cerrada antes de aprobar su costeo.'))
            service = ot.company_id.step_packing_material_cost_service_id
            account = ot.company_id.step_packing_material_cost_account_id
            if not service or not account:
                raise UserError(_('Configure el servicio de costo y la cuenta de consumo de embalajes.'))
            for move in ot.material_picking_id.move_ids.filtered(lambda row: row.state == 'done'):
                if ot.cost_ids.filtered(lambda row: row.material_move_id == move):
                    continue
                value = -sum(move.stock_valuation_layer_ids.mapped('value'))
                if value <= 0:
                    raise UserError(_('El consumo %s necesita una valoración nativa positiva. Revise el costo del material.') % move.product_id.display_name)
                entries = move.stock_valuation_layer_ids.account_move_id
                source = entries.line_ids.filtered(lambda line: line.account_id == account and line.balance > 0)
                if entries and (len(source) != 1 or source.move_id.state != 'posted'):
                    raise UserError(_('La cuenta de consumo debe coincidir con el cargo contable de %s.') % move.product_id.display_name)
                self.env['step.packing.cost'].with_context(_packing_cost=_COST).create({
                    'production_id': ot.id, 'material_move_id': move.id, 'product_id': service.id,
                    'name': _('Consumo %s') % move.product_id.display_name, 'amount': value,
                    'credit_account_id': account.id, 'source_reference': move.picking_id.name,
                    'source_line_id': source.id if len(source) == 1 else False,
                    'export_percent': ot._export_cost_percent()})
        return True

    def _export_cost_percent(self):
        self.ensure_one()
        denominator = self.step_packing_export_kg + self.step_packing_commercial_kg + self.step_packing_precaliber_kg
        return self.step_packing_export_kg / denominator * 100 if denominator else 0

    def _export_cost_moves(self):
        self.ensure_one()
        tags = self.step_packing_output_tag_ids.filtered(lambda tag: tag.step_tag_kind == 'E')
        return self.output_picking_id.move_ids.filtered(lambda move: move.state == 'done' and
            move.location_id.usage == 'production' and move.location_dest_id.usage == 'internal' and
            move.move_line_ids and all(not line.owner_id and line.result_package_id in tags for line in move.move_line_ids))

    def _check_cost_sources(self):
        self.cost_ids._check_values()
        sources = self.cost_ids.source_line_id.sorted('id')
        if sources:
            self.env.cr.execute('SELECT id FROM account_move_line WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sources.ids)])
            for source in sources:
                costs = self.env['step.packing.cost'].search([('source_line_id', '=', source.id)])
                if float_compare(sum(costs.mapped('amount')), source.balance, precision_rounding=source.company_currency_id.rounding) > 0:
                    raise UserError(_('El gasto %s se asignó por sobre su importe contable.') % source.move_id.display_name)

    def action_approve_costs(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('El costeo requiere un administrador de Inventario.'))
        self._lock_process()
        for ot in self:
            if ot.state != 'closed' or not ot.cost_ids:
                raise UserError(_('Cierre la OT y registre sus costos antes de aprobar.'))
            if any(not row.source_line_id and not (row.source_reference or '').strip() for row in ot.cost_ids):
                raise UserError(_('Identifique el respaldo de cada costo.'))
            ot.cost_ids._check_values()
            ot._check_cost_sources()
            ot.with_context(_packing_control=_INTERNAL, _packing_cost=_COST).write({
                'state': 'costed', 'cost_approved_by': self.env.uid, 'cost_approved_at': fields.Datetime.now()})
        return True

    def action_reopen_costs(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('La revisión requiere un administrador de Inventario.'))
        self._lock_process()
        if any(ot.state != 'costed' or ot.landed_cost_id for ot in self):
            raise UserError(_('Solo se reabre un costeo aprobado que aún no se ha capitalizado.'))
        self.with_context(_packing_control=_INTERNAL, _packing_cost=_COST).write({
            'state': 'closed', 'cost_approved_by': False, 'cost_approved_at': False})
        return True

    def action_capitalize_costs(self):
        if not self.env.user.has_group('account.group_account_user') or not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('La capitalización requiere Contabilidad y administración de Inventario.'))
        self._lock_process()
        with self.env.cr.savepoint():
            for ot in self:
                if ot.state == 'accounted' and ot.landed_cost_id.state == 'done':
                    continue
                if ot.state != 'costed' or ot.landed_cost_id:
                    raise UserError(_('Apruebe el costeo antes de capitalizarlo.'))
                moves = ot._export_cost_moves()
                lines = ot.cost_ids.filtered(lambda row: row.capitalizable_amount > 0)
                if not moves or not lines or any(move.product_id.cost_method not in ('fifo', 'average') or move.product_id.valuation != 'real_time' for move in moves):
                    raise UserError(_('La capitalización requiere fruta E propia con valoración automática FIFO/promedio y costos capitalizables.'))
                journal = ot.company_id.lc_journal_id
                if not journal or journal.type != 'general':
                    raise UserError(_('Configure el diario nativo de costos en destino de esta empresa.'))
                ot._check_cost_sources()
                cost = self.env['stock.landed.cost'].with_context(_packing_cost=_COST).create({
                    'step_packing_production_id': ot.id, 'company_id': ot.company_id.id, 'date': ot.date,
                    'account_journal_id': journal.id, 'picking_ids': [(6, 0, ot.output_picking_id.ids)],
                    'cost_lines': [(0, 0, {'name': row.name, 'product_id': row.product_id.id,
                        'price_unit': row.capitalizable_amount, 'account_id': row.credit_account_id.id,
                        'split_method': 'by_weight'}) for row in lines]})
                cost.compute_landed_cost()
                cost.with_context(_packing_cost=_COST).button_validate()
                ot.with_context(_packing_control=_INTERNAL, _packing_cost=_COST).write({'landed_cost_id': cost.id, 'state': 'accounted'})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if any(row.get('cost_approved_by') or row.get('cost_approved_at') or row.get('landed_cost_id') for row in vals_list):
            raise UserError(_('Use las acciones de costeo.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'cost_approved_by', 'cost_approved_at', 'landed_cost_id'} & vals.keys() and self.env.context.get('_packing_cost') is not _COST:
            raise UserError(_('Use las acciones de costeo.'))
        if set(vals) == {'cost_ids'}:
            self._lock_process()
            if any(row.state != 'closed' for row in self):
                raise UserError(_('Los costos se editan únicamente en OT cerradas sin costeo aprobado.'))
            return super(PackingProduction, self.with_context(_packing_control=_INTERNAL)).write(vals)
        return super().write(vals)


class LandedCostLine(models.Model):
    _inherit = 'stock.landed.cost.lines'

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env['stock.landed.cost'].browse([row.get('cost_id') for row in vals_list if row.get('cost_id')])
        if parents.step_packing_production_id and self.env.context.get('_packing_cost') is not _COST:
            raise UserError(_('Los costos capitalizados provienen de la OT aprobada.'))
        return super().create(vals_list)

    def write(self, vals):
        if ('cost_id' in vals or self.cost_id.step_packing_production_id) and self.env.context.get('_packing_cost') is not _COST:
            if self.cost_id.step_packing_production_id or 'cost_id' in vals and self.env['stock.landed.cost'].browse(vals['cost_id']).step_packing_production_id:
                raise UserError(_('Los costos capitalizados conservan la revisión de la OT.'))
        return super().write(vals)

    def unlink(self):
        if self.cost_id.step_packing_production_id and self.env.context.get('_packing_cost') is not _COST:
            raise UserError(_('No se eliminan costos capitalizados de Packing.'))
        return super().unlink()


class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'
    step_packing_production_id = fields.Many2one('step.packing.production', readonly=True, copy=False, check_company=True)
    _sql_constraints = [('packing_cost_unique', 'unique(step_packing_production_id)', 'La OT ya tiene una capitalización.')]

    def _get_targeted_move_ids(self):
        if self.step_packing_production_id:
            return self.step_packing_production_id._export_cost_moves()
        return super()._get_targeted_move_ids()

    def get_valuation_lines(self):
        values = super().get_valuation_lines()
        if self.step_packing_production_id:
            for row in values:
                move = self.env['stock.move'].browse(row['move_id'])
                tags = move.move_line_ids.result_package_id
                row['weight'] = sum(tags.step_tag_line_ids.filtered(lambda line: line.product_id == move.product_id).mapped('kilos'))
                if row['weight'] <= 0:
                    raise UserError(_('Cada producto E necesita kilos reales para distribuir la capitalización.'))
        return values

    @api.model_create_multi
    def create(self, vals_list):
        if any(row.get('step_packing_production_id') for row in vals_list) and self.env.context.get('_packing_cost') is not _COST:
            raise UserError(_('Genere la capitalización desde la OT aprobada.'))
        return super().create(vals_list)

    def write(self, vals):
        if ('step_packing_production_id' in vals or self.step_packing_production_id) and self.env.context.get('_packing_cost') is not _COST:
            raise UserError(_('La capitalización de Packing conserva el costeo aprobado.'))
        return super().write(vals)

    def button_validate(self):
        if self.step_packing_production_id and self.env.context.get('_packing_cost') is not _COST:
            raise UserError(_('Capitalice desde la OT aprobada.'))
        return super().button_validate()

    def button_cancel(self):
        if self.step_packing_production_id:
            raise UserError(_('La capitalización conserva su vínculo con la OT.'))
        return super().button_cancel()

    def unlink(self):
        if self.step_packing_production_id:
            raise UserError(_('No se elimina una capitalización de Packing.'))
        return super().unlink()


class ValuationAdjustment(models.Model):
    _inherit = 'stock.valuation.adjustment.lines'

    @api.model_create_multi
    def create(self, vals_list):
        costs = self.env['stock.landed.cost'].browse([row.get('cost_id') for row in vals_list if row.get('cost_id')])
        if costs.step_packing_production_id and self.env.context.get('_packing_cost') is not _COST:
            raise UserError(_('Calcule la distribución desde el costeo aprobado.'))
        return super().create(vals_list)

    def write(self, vals):
        target = self.env['stock.landed.cost'].browse(vals.get('cost_id'))
        if (self.cost_id | target).step_packing_production_id and self.env.context.get('_packing_cost') is not _COST:
            raise UserError(_('La distribución conserva los kilos y costos aprobados de la OT.'))
        return super().write(vals)

    def unlink(self):
        if self.cost_id.step_packing_production_id and self.env.context.get('_packing_cost') is not _COST:
            raise UserError(_('No se elimina la distribución aprobada de Packing.'))
        return super().unlink()


class AccountingMove(models.Model):
    _inherit = 'account.move'

    def _check_packing_cost_documents(self):
        if self.env['stock.landed.cost'].search_count([('account_move_id', 'in', self.ids), ('step_packing_production_id', '!=', False)]):
            raise UserError(_('El asiento pertenece a una capitalización de Packing y conserva su valoración.'))
        if self.env['step.packing.cost'].search_count([('source_line_id.move_id', 'in', self.ids), ('production_id.state', 'in', ['costed', 'accounted'])]):
            raise UserError(_('El gasto respalda un costeo aprobado y conserva su importe contable.'))

    def button_draft(self):
        self._check_packing_cost_documents()
        return super().button_draft()

    def button_cancel(self):
        self._check_packing_cost_documents()
        return super().button_cancel()
