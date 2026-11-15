from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError


_GUIDE_CONTAINER = object()


class DispatchGuide(models.Model):
    _inherit = 'step.dispatch.guide'

    step_container_transfer_ids = fields.One2many('step.harvest.container.transfer', 'dispatch_guide_id',
                                                  string='Entrega de envases', copy=False)

    def _step_billable_lines(self):
        return super()._step_billable_lines().filtered(lambda line: not line._step_is_returnable_container())

    def _step_pallet_detail_lines(self):
        lines = super()._step_pallet_detail_lines()
        if self.step_recipient_kind in ('customer', 'producer', False) and not self.dispatch_instruction_id:
            lines -= lines.filtered(lambda line: line._step_is_returnable_container()
                                    and line.product_id not in self.load_tag_ids.step_tag_line_ids.product_id)
        return lines

    @api.depends('line_ids.step_container_returnable', 'line_ids.product_id.step_is_harvest_container', 'state')
    def _compute_totals(self):
        return super()._compute_totals()

    @api.depends('line_ids.step_container_returnable', 'line_ids.product_id.step_is_harvest_container')
    def _compute_invoice_status(self):
        return super()._compute_invoice_status()

    def action_confirm(self):
        with self.env.cr.savepoint():
            for guide in self.sorted('id'):
                self.env.cr.execute('SELECT id FROM step_dispatch_guide WHERE id=%s FOR UPDATE', [guide.id])
                guide.invalidate_recordset()
                if guide.state == 'confirmed':
                    continue
                if guide.state != 'draft':
                    raise UserError(_('Devuelva la guía a borrador antes de confirmarla.'))
                lines = guide.line_ids.filtered('product_id.step_is_harvest_container')
                guide.line_ids.with_context(_step_guide_container=_GUIDE_CONTAINER).write({
                    'step_container_returnable': False})
                lines.with_context(_step_guide_container=_GUIDE_CONTAINER).write({'step_container_returnable': True})
                super(DispatchGuide, guide).action_confirm()
                if lines and guide.step_recipient_kind in ('producer', 'customer', False):
                    guide._step_issue_containers(lines)
        return True

    def _step_issue_containers(self, lines):
        self.ensure_one()
        if self.picking_id.move_ids.product_id & lines.product_id:
            raise UserError(_('La operación de inventario de la guía ya incluye los envases. '
                              'Quite esas líneas del traslado de fruta para no descontar dos veces.'))
        warehouses = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)])
        warehouse = self.step_source_warehouse_id or self.picking_id.picking_type_id.warehouse_id or (
            warehouses if len(warehouses) == 1 else warehouses.browse())
        if not warehouse:
            raise UserError(_('Seleccione el almacén de origen de los envases.'))
        transfer = self.env['step.harvest.container.transfer'].with_context(
            _step_guide_container=_GUIDE_CONTAINER, mail_create_nosubscribe=True).create({
            'dispatch_guide_id': self.id, 'company_id': self.company_id.id, 'warehouse_id': warehouse.id,
            'producer_id': self.partner_id.id, 'direction': 'issue',
            'line_ids': [Command.create({
                'product_id': line.product_id.id, 'lot_id': line.lot_id.id,
                'quantity': line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id),
            }) for line in lines],
        })
        transfer.action_validate()

    def _step_check_container_ledger(self):
        if self.filtered('step_container_transfer_ids'):
            raise UserError(_('Esta guía respalda una entrega de envases validada. Conserve la guía y '
                              'registre cualquier devolución en Control de Envases.'))

    def action_cancel(self):
        self._step_check_container_ledger()
        return super().action_cancel()

    def action_draft(self):
        self._step_check_container_ledger()
        return super().action_draft()

    def write(self, values):
        if {'state', 'company_id', 'line_ids', 'partner_id', 'step_source_warehouse_id', 'dispatch_type_id',
            'picking_id', 'transfer_reason_id'} & values.keys():
            self._step_check_container_ledger()
        return super().write(values)

    def unlink(self):
        self._step_check_container_ledger()
        return super().unlink()


class DispatchGuideLine(models.Model):
    _inherit = 'step.dispatch.guide.line'

    step_container_returnable = fields.Boolean(string='Envase retornable emitido', readonly=True, copy=False)

    def _step_is_returnable_container(self):
        self.ensure_one()
        return (self.product_id.step_is_harvest_container if self.guide_id.state == 'draft'
                else self.step_container_returnable)

    @api.model_create_multi
    def create(self, vals_list):
        self.env['step.dispatch.guide'].browse([vals['guide_id'] for vals in vals_list if vals.get('guide_id')]
                                              )._step_check_container_ledger()
        if any(vals.get('step_container_returnable') for vals in vals_list):
            raise UserError(_('Los envases retornables se registran al emitir la guía.'))
        return super().create(vals_list)

    def write(self, values):
        self.guide_id._step_check_container_ledger()
        if 'step_container_returnable' in values and self.env.context.get('_step_guide_container') is not _GUIDE_CONTAINER:
            raise UserError(_('Los envases retornables se registran al emitir la guía.'))
        if values.get('guide_id'):
            self.env['step.dispatch.guide'].browse(values['guide_id'])._step_check_container_ledger()
        return super().write(values)

    def unlink(self):
        self.guide_id._step_check_container_ledger()
        return super().unlink()


class ContainerTransfer(models.Model):
    _inherit = 'step.harvest.container.transfer'

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('_step_guide_container') is not _GUIDE_CONTAINER and any(
                vals.get('dispatch_guide_id') for vals in vals_list):
            raise UserError(_('El vínculo con la guía se genera al emitir el documento.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'dispatch_guide_id' in vals:
            raise UserError(_('Conserve el vínculo entre el movimiento de envases y la guía.'))
        return super().write(vals)
