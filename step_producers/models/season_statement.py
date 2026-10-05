"""Season statements group existing settlements; they never duplicate invoices."""
import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_TRANSITION = object()


class SeasonStatement(models.Model):
    _name = 'step.producer.season.statement'
    _description = 'Consolidado de temporada del productor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'id desc'

    name = fields.Char(required=True, default='Nuevo', readonly=True, copy=False)
    state = fields.Selection([('draft', 'Generado'), ('confirmed', 'Confirmado'), ('closed', 'Cerrado')], default='draft', required=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    producer_id = fields.Many2one('res.partner', string='Productor', required=True)
    season_id = fields.Many2one('step.temporada', string='Temporada', required=True, check_company=True)
    date_start = fields.Date('Desde')
    date_end = fields.Date('Hasta')
    transport_type = fields.Selection([('sea', 'Marítimo'), ('air', 'Aéreo'), ('land', 'Terrestre')], string='Transporte')
    variety_ids = fields.Many2many('step.variedad', string='Variedades')
    shipment_ids = fields.Many2many('step.export.export', string='Embarques')
    settlement_ids = fields.Many2many('step.export.producer.settlement', relation='step_season_statement_settlement_rel', string='Liquidaciones incluidas', copy=False)
    scope_key = fields.Char(required=True, readonly=True, copy=False)
    usd_currency_id = fields.Many2one('res.currency', default=lambda self: self.env.ref('base.USD'), required=True)
    total_kg = fields.Float('Kilos', compute='_compute_totals')
    gross_usd = fields.Monetary('Bruto USD', currency_field='usd_currency_id', compute='_compute_totals')
    discount_usd = fields.Monetary('Descuentos USD', currency_field='usd_currency_id', compute='_compute_totals')
    net_usd = fields.Monetary('Neto USD', currency_field='usd_currency_id', compute='_compute_totals')
    bill_ids = fields.Many2many('account.move', compute='_compute_totals', string='Documentos contables')

    _sql_constraints = [('scope_unique', 'unique(company_id, scope_key)', 'Este consolidado ya existe.')]

    @api.depends('settlement_ids.total_kg', 'settlement_ids.gross_usd', 'settlement_ids.discount_usd', 'settlement_ids.net_usd', 'settlement_ids.bill_id')
    def _compute_totals(self):
        for record in self:
            record.total_kg = sum(record.settlement_ids.mapped('total_kg'))
            record.gross_usd = sum(record.settlement_ids.mapped('gross_usd'))
            record.discount_usd = sum(record.settlement_ids.mapped('discount_usd'))
            record.net_usd = sum(record.settlement_ids.mapped('net_usd'))
            record.bill_ids = record.settlement_ids.mapped('bill_id')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'draft') != 'draft':
                raise UserError(_('El consolidado se crea en estado Generado.'))
            vals['name'] = self.env['ir.sequence'].next_by_code(self._name) or 'Nuevo'
        return super().create(vals_list)

    @api.constrains('settlement_ids', 'company_id', 'producer_id', 'season_id', 'date_start', 'date_end')
    def _check_scope(self):
        for record in self:
            if record.date_start and record.date_end and record.date_end < record.date_start:
                raise ValidationError(_('Revise el período del consolidado.'))
            for settlement in record.settlement_ids:
                if (settlement.company_id != record.company_id or settlement.producer_id != record.producer_id or
                    settlement.receiver_settlement_id.season_id != record.season_id):
                    raise ValidationError(_('Todas las liquidaciones deben corresponder al productor, empresa y temporada.'))
                if settlement.state not in ('validated', 'accounted', 'closed'):
                    raise ValidationError(_('Valide cada liquidación antes de consolidarla.'))

    def action_confirm(self):
        self.check_access('write')
        for record in self:
            record._lock_statement()
            if record.state != 'draft' or not record.settlement_ids:
                raise UserError(_('Seleccione liquidaciones validadas en un consolidado generado.'))
            record._check_scope()
            record.with_context(_season_transition=_TRANSITION).write({'state': 'confirmed'})
        return True

    def action_close(self):
        for record in self:
            record._lock_statement()
            if record.state != 'confirmed' or any(row.state != 'closed' for row in record.settlement_ids):
                raise UserError(_('Cierre las liquidaciones individuales antes de cerrar el consolidado.'))
            record.with_context(_season_transition=_TRANSITION).write({'state': 'closed'})
        return True

    def _lock_statement(self):
        self.check_access('write')
        if self:
            self.env.cr.execute('SELECT id FROM step_producer_season_statement WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset()
            children = self.settlement_ids
            if children:
                self.env.cr.execute('SELECT id FROM step_export_producer_settlement WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(children.ids))])
                children.invalidate_recordset()

    def write(self, vals):
        if 'state' in vals and self.env.context.get('_season_transition') is not _TRANSITION:
            raise UserError(_('Use las acciones de confirmación y cierre.'))
        if vals.keys() - {'state'} and any(row.state != 'draft' for row in self):
            raise UserError(_('Un consolidado confirmado conserva su selección. Genere otro para ampliar el alcance.'))
        if {'scope_key', 'company_id', 'producer_id', 'season_id', 'settlement_ids'} & vals.keys():
            raise UserError(_('La selección se genera desde el asistente; no se cambia manualmente.'))
        return super().write(vals)

    def unlink(self):
        if any(row.state != 'draft' for row in self):
            raise UserError(_('No se elimina un consolidado confirmado.'))
        return super().unlink()


class SeasonStatementWizard(models.TransientModel):
    _name = 'step.producer.season.statement.wizard'
    _description = 'Generar consolidados por temporada'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    season_id = fields.Many2one('step.temporada', string='Temporada', required=True)
    producer_ids = fields.Many2many('res.partner', string='Productores', domain="[('is_productor','=',True)]")
    date_start = fields.Date('Liquidación desde')
    date_end = fields.Date('Liquidación hasta')
    transport_type = fields.Selection([('sea', 'Marítimo'), ('air', 'Aéreo'), ('land', 'Terrestre')], string='Transporte')
    variety_ids = fields.Many2many('step.variedad', string='Variedades')
    shipment_ids = fields.Many2many('step.export.export', string='Embarques')

    def action_generate(self):
        self.ensure_one()
        if self.company_id not in self.env.companies:
            raise UserError(_('Seleccione una empresa habilitada.'))
        if self.date_start and self.date_end and self.date_end < self.date_start:
            raise ValidationError(_('Revise el período seleccionado.'))
        domain = [('company_id', '=', self.company_id.id), ('receiver_settlement_id.season_id', '=', self.season_id.id),
                  ('state', 'in', ['validated', 'accounted', 'closed'])]
        if self.producer_ids:
            domain.append(('producer_id', 'in', self.producer_ids.ids))
        if self.date_start:
            domain.append(('receiver_settlement_id.date', '>=', self.date_start))
        if self.date_end:
            domain.append(('receiver_settlement_id.date', '<=', self.date_end))
        settlements = self.env['step.export.producer.settlement'].search(domain)
        selected = self.env['step.export.producer.settlement']
        for settlement in settlements:
            tags = settlement.line_ids.mapped('tag_id')
            shipments = settlement.receiver_settlement_id.line_ids.filtered(lambda line: bool(line.shipment_id.tag_ids & tags)).mapped('shipment_id')
            if self.variety_ids and any(tag.variedad_id not in self.variety_ids for tag in tags):
                continue
            if self.shipment_ids and (not shipments or any(row not in self.shipment_ids for row in shipments)):
                continue
            if self.transport_type and (not shipments or any(row.transport_type != self.transport_type for row in shipments)):
                continue
            selected |= settlement
        if not selected:
            raise UserError(_('No hay liquidaciones completas y validadas para estos filtros.'))
        statements = self.env['step.producer.season.statement']
        # Repeated clicks reuse the same producer/settlement set. No invoice is created here.
        with self.env.cr.savepoint():
            self.env.cr.execute('SELECT id FROM res_company WHERE id=%s FOR UPDATE', [self.company_id.id])
            for producer in selected.mapped('producer_id'):
                group = selected.filtered(lambda row: row.producer_id == producer)
                key = hashlib.sha256(json.dumps((producer.id, self.season_id.id, sorted(group.ids))).encode()).hexdigest()
                statement = statements.search([('company_id', '=', self.company_id.id), ('scope_key', '=', key)], limit=1)
                if not statement:
                    statement = statements.create({
                        'company_id': self.company_id.id, 'producer_id': producer.id, 'season_id': self.season_id.id,
                        'scope_key': key, 'date_start': self.date_start, 'date_end': self.date_end,
                        'transport_type': self.transport_type, 'variety_ids': [(6, 0, self.variety_ids.ids)],
                        'shipment_ids': [(6, 0, self.shipment_ids.ids)], 'settlement_ids': [(6, 0, group.ids)],
                    })
                statements |= statement
        return {'type': 'ir.actions.act_window', 'name': _('Consolidados generados'),
                'res_model': statements._name, 'view_mode': 'list,form', 'domain': [('id', 'in', statements.ids)]}


class ProducerSettlement(models.Model):
    _inherit = 'step.export.producer.settlement'

    def action_reopen(self):
        self.check_access('write')
        if self:
            self.env.cr.execute('SELECT id FROM step_export_producer_settlement WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset()
        if self.env['step.producer.season.statement'].search_count([
                ('settlement_ids', 'in', self.ids), ('state', 'in', ['confirmed', 'closed'])]):
            raise UserError(_('La liquidación forma parte de un consolidado confirmado y conserva sus importes.'))
        return super().action_reopen()
