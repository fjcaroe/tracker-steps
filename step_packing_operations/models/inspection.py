"""Record internal/SAG results in Odoo; official certificates are supplied externally."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_RESULT = object()


class PackingInspection(models.Model):
    _name = 'step.packing.inspection'
    _description = 'Inspección de fruta de Packing'
    _check_company_auto = True
    _order = 'date desc, id desc'
    name = fields.Char('Referencia', required=True)
    production_id = fields.Many2one('step.packing.production', string='OT', required=True, ondelete='restrict', check_company=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True)
    kind = fields.Selection([('internal', 'Interna'), ('sag', 'SAG')], string='Inspección', required=True)
    date = fields.Date('Fecha', required=True, default=fields.Date.context_today)
    inspector_id = fields.Many2one('res.partner', string='Inspector', required=True)
    package_ids = fields.Many2many('stock.quant.package', relation='step_packing_inspection_package_rel', string='Tarjas', required=True)
    output_package_ids = fields.Many2many(related='production_id.step_packing_output_tag_ids')
    certificate_reference = fields.Char('Referencia certificado externo')
    observations = fields.Text('Resultado / observaciones')
    state = fields.Selection([('draft', 'Borrador'), ('approved', 'Aprobada'), ('rejected', 'Rechazada')], default='draft', required=True, copy=False)
    reviewed_by = fields.Many2one('res.users', readonly=True, copy=False)
    reviewed_at = fields.Datetime(readonly=True, copy=False)

    @api.constrains('package_ids', 'production_id')
    def _check_packages(self):
        for record in self:
            if not record.package_ids or record.package_ids - record.production_id.step_packing_output_tag_ids:
                raise ValidationError(_('Seleccione tarjas resultantes de esta OT.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'draft') != 'draft' or vals.get('reviewed_by') or vals.get('reviewed_at'):
                raise UserError(_('Las inspecciones se crean en borrador.'))
        return super().create(vals_list)

    def _review(self, approved):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_('La revisión requiere un administrador de Inventario.'))
        self.check_access('write')
        self.production_id._lock_process()
        for record in self:
            self.env.cr.execute('SELECT id FROM step_packing_inspection WHERE id=%s FOR UPDATE', [record.id])
            record.invalidate_recordset()
            if record.state != 'draft' or record.production_id.state != 'closed' or any(tag.step_tag_state != 'validated' for tag in record.package_ids):
                raise UserError(_('Revise una inspección en borrador de una OT cerrada con tarjas disponibles.'))
            if approved and record.kind == 'sag' and not (record.certificate_reference or '').strip():
                raise UserError(_('Registre la referencia del certificado emitido externamente por SAG.'))
            if not approved and not (record.observations or '').strip():
                raise UserError(_('Indique el motivo del rechazo.'))
            record.with_context(_inspection_result=_RESULT).write({'state': 'approved' if approved else 'rejected',
                'reviewed_by': self.env.uid, 'reviewed_at': fields.Datetime.now()})
        return True

    def action_approve(self):
        return self._review(True)

    def action_reject(self):
        return self._review(False)

    def write(self, vals):
        if self:
            self.env.cr.execute('SELECT id FROM step_packing_inspection WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset()
        if self.env.context.get('_inspection_result') is not _RESULT:
            if any(row.state != 'draft' for row in self) or {'state', 'reviewed_by', 'reviewed_at'} & vals.keys():
                raise UserError(_('La inspección revisada conserva su resultado. Cree una nueva inspección para reevaluar.'))
        return super().write(vals)

    def unlink(self):
        self.check_access('unlink')
        if self:
            self.env.cr.execute('SELECT id FROM step_packing_inspection WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset()
        if any(row.state != 'draft' for row in self):
            raise UserError(_('No se elimina una inspección revisada.'))
        return super().unlink()


class PackingProduction(models.Model):
    _inherit = 'step.packing.production'
    required_inspection = fields.Selection([('none', 'Sin inspección obligatoria'), ('internal', 'Interna'), ('sag', 'SAG')], default='none', required=True, string='Inspección exigida')
    inspection_ids = fields.One2many('step.packing.inspection', 'production_id', string='Inspecciones')

    def write(self, vals):
        if 'required_inspection' in vals and any(row.state != 'created' for row in self):
            raise UserError(_('Defina la inspección exigida antes de validar la OT.'))
        return super().write(vals)


class ExportShipment(models.Model):
    _inherit = 'step.export.export'

    def _check_tag_load(self):
        result = super()._check_tag_load()
        for shipment in self:
            productions = self.env['step.packing.production'].search([('step_packing_output_tag_ids', 'in', shipment.tag_ids.ids)])
            productions._lock_process()
            for production in productions:
                for package in production.step_packing_output_tag_ids & shipment.tag_ids:
                    inspections = production.inspection_ids.filtered(lambda row: package in row.package_ids and row.state != 'draft').sorted('id', reverse=True)
                    latest_by_kind = {kind: inspections.filtered(lambda row: row.kind == kind)[:1] for kind in ('internal', 'sag')}
                    if any(row and row.state == 'rejected' for row in latest_by_kind.values()):
                        raise UserError(_('La tarja %s tiene una inspección rechazada; registre una reevaluación aprobada.') % package.name)
                    required = latest_by_kind.get(production.required_inspection)
                    if production.required_inspection != 'none' and (not required or required.state != 'approved'):
                        raise UserError(_('Complete la inspección exigida para la tarja %s antes de despachar.') % package.name)
        return result
