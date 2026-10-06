"""Separate reviewed IVV provision from the official export adjustment note."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_IVV = object()


class Company(models.Model):
    _inherit = 'res.company'
    step_export_liquidation_journal_id = fields.Many2one('account.journal', string='Diario provisión liquidaciones', check_company=True,
        domain="[('type','=','general')]")

    @api.constrains('step_export_liquidation_journal_id')
    def _check_liquidation_journal(self):
        for company in self:
            journal = company.step_export_liquidation_journal_id
            if journal and (journal.type != 'general' or journal.company_id != company):
                raise ValidationError(_('Use un diario general de esta empresa para provisionar liquidaciones.'))


class ReceiverSettlement(models.Model):
    _inherit = 'step.export.receiver.settlement'
    ivv_provisioned = fields.Boolean('IVV provisionado', readonly=True, copy=False)
    provision_move_ids = fields.One2many('account.move', 'step_export_provision_settlement_id', string='Provisión y reversión')
    adjustment_date = fields.Date('Fecha nota definitiva')

    def action_validate(self):
        self._lock_ivv()
        with self.env.cr.savepoint():
            return super().action_validate()

    def _lock_ivv(self):
        self.check_access('write')
        if self:
            self.env.cr.execute('SELECT id FROM step_export_receiver_settlement WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset()

    def action_provision_ivv(self):
        if not self.env.user.has_group('account.group_account_user'):
            raise UserError(_('La provisión requiere permisos de Contabilidad.'))
        self._lock_ivv()
        with self.env.cr.savepoint():
            for record in self:
                if record.ivv_provisioned:
                    if any(move.state != 'posted' for move in record.provision_move_ids):
                        raise UserError(_('La provisión existente debe permanecer publicada.'))
                    continue
                if record.state != 'validated':
                    raise UserError(_('Revise y valide el IVV antes de provisionarlo.'))
                journal = record.company_id.step_export_liquidation_journal_id
                if not journal:
                    raise UserError(_('Configure el diario Provisión liquidaciones en los parámetros contables.'))
                for line in record.line_ids:
                    difference = record.usd_currency_id.round(line.difference_usd)
                    if not difference:
                        continue
                    invoice = line.invoice_id
                    receivable = invoice.line_ids.filtered(lambda item: item.account_id.account_type == 'asset_receivable')[:1].account_id
                    income = invoice.invoice_line_ids.filtered(lambda item: item.display_type == 'product' and item.account_id)[:1].account_id
                    if invoice.state != 'posted' or invoice.partner_id.commercial_partner_id != record.receiver_id.commercial_partner_id or not receivable or not income:
                        raise UserError(_('La factura inicial debe estar publicada y tener cuentas de clientes e ingresos del recibidor.'))
                    signed = record.usd_currency_id._convert(difference, record.company_id.currency_id, record.company_id, record.date)
                    move = self.env['account.move'].with_company(record.company_id).with_context(_ivv_transition=_IVV).create({
                        'move_type': 'entry', 'journal_id': journal.id, 'company_id': record.company_id.id, 'date': record.date,
                        'ref': '%s / Provisión IVV revisado / %s' % (record.name, line.shipment_id.display_name),
                        'step_export_provision_settlement_id': record.id,
                        'line_ids': [(0, 0, {'name': record.name, 'account_id': account.id, 'partner_id': record.receiver_id.id,
                            'currency_id': record.usd_currency_id.id, 'amount_currency': foreign,
                            'debit': max(balance, 0), 'credit': max(-balance, 0)})
                            for account, balance, foreign in ((receivable, signed, difference), (income, -signed, -difference))]})
                    move.action_post()
                record.with_context(_ivv_transition=_IVV).write({'ivv_provisioned': True})
        return True

    def action_account(self):
        if not self.env.user.has_group('account.group_account_user'):
            raise UserError(_('Las notas definitivas requieren permisos de Contabilidad.'))
        self._lock_ivv()
        with self.env.cr.savepoint():
            for record in self:
                if record.state == 'accounted':
                    continue
                record.action_provision_ivv()
                if not record.adjustment_date:
                    raise UserError(_('Indique la fecha de la nota definitiva.'))
                if record.adjustment_date < record.date:
                    raise UserError(_('La nota definitiva no puede ser anterior a la provisión.'))
                provisions = record.provision_move_ids.filtered(lambda move: not move.reversed_entry_id)
                super(ReceiverSettlement, record).action_account()
                # Exact reversal removes the provisional recognition. The official
                # note uses its own document date/rate and remains the definitive balance.
                for provision in provisions:
                    if provision.reversal_move_ids:
                        raise UserError(_('La provisión ya tiene una reversión; revise su trazabilidad.'))
                    reversal = provision.with_context(_ivv_transition=_IVV)._reverse_moves(default_values_list=[{
                        'date': record.adjustment_date, 'ref': '%s / Reversión por nota definitiva' % record.name,
                        'step_export_provision_settlement_id': record.id}])
                    reversal.action_post()
                    for account in provision.line_ids.account_id.filtered(lambda row: row.reconcile):
                        (provision.line_ids | reversal.line_ids).filtered(lambda row: row.account_id == account and not row.reconciled).reconcile()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if any(row.get('ivv_provisioned') or row.get('provision_move_ids') for row in vals_list):
            raise UserError(_('Use las acciones de provisión.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'ivv_provisioned', 'provision_move_ids'} & vals.keys() and self.env.context.get('_ivv_transition') is not _IVV:
            raise UserError(_('Use las acciones de provisión.'))
        if 'adjustment_date' in vals and any(row.state == 'accounted' for row in self):
            raise UserError(_('La nota contabilizada conserva su fecha.'))
        return super().write(vals)


class SettlementLine(models.Model):
    _inherit = 'step.export.receiver.settlement.line'

    def write(self, vals):
        if set(vals) == {'external_adjustment_folio'}:
            self.settlement_id._lock_ivv()
            if any(row.settlement_id.state == 'accounted' for row in self):
                raise UserError(_('La nota contabilizada conserva su folio.'))
            # Issuer folio arrives after the reviewed amounts have been frozen.
            return super().write(vals)
        return super().write(vals)


class AccountMove(models.Model):
    _inherit = 'account.move'
    step_export_provision_settlement_id = fields.Many2one('step.export.receiver.settlement', copy=False, readonly=True, ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        if any(row.get('step_export_provision_settlement_id') for row in vals_list) and self.env.context.get('_ivv_transition') is not _IVV:
            raise UserError(_('La provisión se genera desde la liquidación revisada.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'step_export_provision_settlement_id' in vals and self.env.context.get('_ivv_transition') is not _IVV:
            raise UserError(_('La provisión conserva su liquidación de origen.'))
        return super().write(vals)

    def button_draft(self):
        if self.step_export_provision_settlement_id:
            raise UserError(_('La provisión y su reversión conservan sus asientos publicados.'))
        return super().button_draft()

    def button_cancel(self):
        if self.step_export_provision_settlement_id:
            raise UserError(_('La provisión se revierte mediante la nota definitiva.'))
        return super().button_cancel()
