from odoo import api, models, _
from odoo.exceptions import AccessError, UserError

_RECEIVING = object()
_KEY = '_cerro_process_receipt'


def _receiving(records):
    return records.env.context.get(_KEY) is _RECEIVING


def _scoped(records):
    return records.with_context(**{_KEY: _RECEIVING})


class Picking(models.Model):
    _inherit = 'stock.picking'

    def action_step_container_return(self):
        self.ensure_one()
        self.check_access('write')
        return super(Picking, _scoped(self)).action_step_container_return()

    def button_validate(self):
        self.check_access('write')
        pending = self.filtered(lambda picking: picking.state not in ('done', 'cancel'))
        if pending:
            self.env.cr.execute("""
                SELECT EXISTS (SELECT FROM stock_picking WHERE id = ANY(%s)
                    AND (step_interplant_guide_id IS NOT NULL OR step_dispatch_origin_guide_id IS NOT NULL))
            """, (pending.ids,))
            if self.env.cr.fetchone()[0]:
                raise UserError(_('La guía de este traslado requiere la validación de movimientos interplanta.'))
        fruit = pending.filtered('step_fruit_reception_kind')
        if not fruit:
            return super().button_validate()
        if len(fruit) != len(pending) or any(row.step_fruit_reception_kind != 'process' for row in fruit):
            raise UserError(_('Valide las recepciones de fruta a proceso por separado.'))
        self.env.cr.execute("""
            SELECT EXISTS (SELECT FROM quality_check WHERE picking_id = ANY(%s))
                OR EXISTS (
                    SELECT FROM quality_point qp
                    JOIN quality_point_stock_picking_type_rel rel ON rel.quality_point_id=qp.id
                    JOIN stock_picking p ON p.picking_type_id=rel.stock_picking_type_id
                    WHERE p.id=ANY(%s) AND qp.active AND (qp.company_id IS NULL OR qp.company_id=p.company_id))
        """, (fruit.ids,fruit.ids))
        if self.env.cr.fetchone()[0]:
            raise UserError(_('Se requiere el proveedor operativo de calidad para validar esta recepción.'))
        result = super(Picking, _scoped(self)).button_validate()
        if isinstance(result, dict) and _KEY in (result.get('context') or {}):
            result = dict(result, context={k: v for k, v in result['context'].items() if k != _KEY})
        return result


class Package(models.Model):
    _inherit = 'stock.quant.package'

    def _allows_receipt_stock(self):
        return _receiving(self)

    def _has_archived_shipment(self):
        self.ensure_one()
        self.env.cr.execute("""
            SELECT EXISTS (SELECT FROM step_export_export_stock_quant_package_rel WHERE stock_quant_package_id=%s)
        """, (self.id,))
        return self.env.cr.fetchone()[0]


class FruitLine(models.Model):
    _inherit = 'step.fruit.package.line'

    def _allows_receipt_stock(self):
        return _receiving(self)


class Import(models.TransientModel):
    # This label is the archived ir.model.info on the original assistant (ID 1501).
    # Actual record access is compared on both engines for all fifteen original users.
    __doc__ = (" Model super-class for transient records, meant to be temporarily\n"
               "    persistent, and regularly vacuum-cleaned.\n\n"
               "    A TransientModel has a simplified access rights management, all users can\n"
               "    create new records, and may only access the records they created. The\n"
               "    superuser has unrestricted access to all TransientModel records.\n    ")
    _inherit = 'step.fruit.reception.import'

    def action_import(self):
        self.ensure_one()
        self.picking_id.check_access('write')
        if self.picking_id.state in ('done','cancel') or self.picking_id.step_fruit_reception_kind != 'process':
            raise UserError(_('Seleccione una recepción a proceso abierta.'))
        return super(Import, _scoped(self)).action_import()


class ContainerScope:
    __slots__ = ()

    def _check_access(self, operation):
        if operation != 'read' and not _receiving(self):
            return self, lambda: AccessError(_('Los envases se preparan desde la recepción de fruta.'))
        return super()._check_access(operation)

    @api.model_create_multi
    def create(self, vals_list):
        if not _receiving(self):
            raise AccessError(_('Los envases se preparan desde la recepción de fruta.'))
        return super().create(vals_list)

    def write(self, values):
        raise AccessError(_('El movimiento de envases se conserva como borrador de la recepción.'))

    def unlink(self):
        raise AccessError(_('El movimiento de envases se conserva como borrador de la recepción.'))


class ContainerTransfer(ContainerScope, models.Model):
    _inherit = 'step.harvest.container.transfer'


class ContainerLine(ContainerScope, models.Model):
    _inherit = 'step.harvest.container.transfer.line'
