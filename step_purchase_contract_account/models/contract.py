from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError, ValidationError


class Journal(models.Model):
    _inherit = "account.journal"

    contract_provision_account_id = fields.Many2one(
        "account.account", string="Cuenta de provisión de contratos", check_company=True,
        domain="[('deprecated', '=', False)]",
        help="Cuenta del Haber para provisionar las cuotas del contrato.")


class Contract(models.Model):
    _inherit = "step.management.purchase.contract"

    journal_id = fields.Many2one("account.journal", string="Diario de contrato", check_company=True,
                                 domain="[('type', 'in', ['general', 'purchase'])]")
    accounting_date = fields.Date(string="Fecha contable", default=fields.Date.context_today)
    analytic_distribution = fields.Json(string="Distribución analítica")
    move_ids = fields.One2many("account.move", "purchase_contract_id", string="Comprobantes")

    def _lock_contract(self):
        self.check_access('write')
        self.flush_recordset()
        self.env.cr.execute('SELECT id FROM step_management_purchase_contract WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
        self.invalidate_recordset()
        self.installment_ids.invalidate_recordset()

    def action_post_contract(self):
        self._lock_contract()
        if not self.env.user.has_group('account.group_account_user'):
            raise UserError(_("La contabilización requiere permisos de Contabilidad."))
        for contract in self:
            contract = contract.with_company(contract.company_id)
            if contract.state != 'confirmed' or contract.is_superseded:
                raise UserError(_("Contabilice un contrato confirmado y vigente."))
            journal = contract.journal_id
            if not journal or not contract.accounting_date or not journal.contract_provision_account_id:
                raise UserError(_("Configure el diario, la cuenta de provisión y la fecha contable."))
            if journal.type not in ('general', 'purchase'):
                raise UserError(_("Seleccione un diario de contrato de tipo Varios o Compras."))
            if journal.currency_id and journal.currency_id != contract.currency_id:
                raise UserError(_("La moneda del diario debe coincidir con la del contrato."))
            if contract.installment_ids.filtered(lambda line: line.move_id and line.move_id.state != 'posted'):
                raise UserError(_("Hay comprobantes en borrador o cancelados: revíselos antes de continuar."))
            pending = contract.installment_ids.filtered(lambda line: not line.move_id)
            if any(line.state != 'approved' for line in pending):
                raise UserError(_("Apruebe todas las cuotas pendientes antes de contabilizar."))
            for line in pending:
                debit = (line.product_id.property_account_expense_id
                         or line.product_id.categ_id.property_account_expense_categ_id)
                credit = journal.contract_provision_account_id
                if not debit or debit == credit or debit.deprecated or credit.deprecated:
                    raise UserError(_("Configure cuentas de cargo y provisión distintas y vigentes para %s.") % line.product_id.display_name)
                if contract.company_id not in debit.company_ids or contract.company_id not in credit.company_ids:
                    raise UserError(_("Las cuentas deben pertenecer a la empresa del contrato."))
                amount = contract.currency_id.round(line.amount)
                if amount <= 0:
                    raise UserError(_("La cuota debe tener un importe positivo."))
                balance = contract.currency_id._convert(amount, contract.company_id.currency_id,
                                                        contract.company_id, contract.accounting_date)
                common = {'name': '%s / Cuota %s' % (contract.name, line.sequence),
                          'partner_id': contract.partner_id.id, 'currency_id': contract.currency_id.id,
                          'date_maturity': line.date_due}
                move = self.env['account.move'].create({
                    'move_type': 'entry', 'journal_id': journal.id, 'date': contract.accounting_date,
                    'company_id': contract.company_id.id, 'ref': common['name'],
                    'purchase_contract_id': contract.id,
                    'line_ids': [Command.create(dict(common, account_id=debit.id, debit=balance,
                        credit=0, amount_currency=amount, analytic_distribution=contract.analytic_distribution)),
                        Command.create(dict(common, account_id=credit.id, debit=0, credit=balance,
                                            amount_currency=-amount))]})
                move.action_post()
                line.move_id = move
                line.state = 'posted'
        return True

    def action_revise(self):
        self.ensure_one()
        self._lock_contract()
        # Cuotas pagadas quedan en el contrato original; las no pagadas se reversan.
        pending = self.installment_ids.filtered(lambda line: not line.payment_ids.filtered(lambda p: p.state in ('in_process', 'paid')))
        if any(line.state == 'posted' and not line.move_id for line in pending):
            raise UserError(_("Vincule el comprobante de las cuotas contabilizadas manualmente antes de revisar."))
        posted = pending.filtered('move_id')
        if posted and not self.env.user.has_group('account.group_account_user'):
            raise UserError(_("La reversa de provisiones requiere permisos de Contabilidad."))
        for line in posted:
            if line.move_id.state != 'posted' or line.reversal_move_id:
                raise UserError(_("Revise el estado del comprobante y su reversa antes de continuar."))
        # Valida estado y revisión previa antes de cambiar contabilidad.
        if self.state != 'confirmed' or self.is_superseded:
            raise UserError(_("Sólo se puede revisar un contrato confirmado sin revisión posterior."))
        for line in posted:
            reversal = line.move_id._reverse_moves([{'date': fields.Date.context_today(self),
                'ref': _('Revisión de %s') % self.name}], cancel=True)
            if reversal.state == 'draft':
                reversal.action_post()
            line.reversal_move_id = reversal
        # El método base sólo copia cuotas no contabilizadas. Se cambia el estado
        # de las ya reversadas; el vínculo al asiento original conserva la auditoría.
        posted.write({'state': 'approved'})
        result = super().action_revise()
        return result

    def action_close(self):
        if self.mapped('installment_ids').filtered(lambda line: not line.currency_id.is_zero(line.amount_pending)):
            raise UserError(_("Hay cuotas pendientes de pago; no se puede cerrar el contrato."))
        return super().action_close()

    def write(self, vals):
        protected = {'partner_id', 'company_id', 'currency_id', 'journal_id', 'accounting_date', 'analytic_distribution'}
        if protected.intersection(vals) and self.mapped('move_ids'):
            raise UserError(_("El contrato tiene comprobantes: cree una revisión para cambiar sus datos."))
        return super().write(vals)


class Installment(models.Model):
    _inherit = 'step.management.purchase.contract.installment'

    move_id = fields.Many2one('account.move', string='Comprobante', readonly=True, copy=False, check_company=True)
    reversal_move_id = fields.Many2one('account.move', string='Reversa', readonly=True, copy=False, check_company=True)
    payment_ids = fields.One2many('account.payment', 'purchase_contract_installment_id', string='Pagos')
    amount_paid = fields.Monetary(string='Pagado', compute='_compute_paid')
    amount_pending = fields.Monetary(string='Pendiente de pago', compute='_compute_paid')

    @api.depends('amount', 'payment_ids.state', 'payment_ids.amount')
    def _compute_paid(self):
        for line in self:
            line.amount_paid = sum(line.payment_ids.filtered(lambda p: p.state in ('in_process', 'paid')).mapped('amount'))
            line.amount_pending = max(0, line.amount - line.amount_paid)

    def write(self, vals):
        if {'product_id','quantity','price_unit','date_due','uom_id','contract_id'}.intersection(vals) and self.filtered('move_id'):
            raise UserError(_("No edite una cuota contabilizada; revise las condiciones del contrato."))
        return super().write(vals)

    @api.constrains('move_id', 'state')
    def _check_posted_move(self):
        for line in self:
            if line.state == 'posted' and not line.move_id:
                raise ValidationError(_('Una cuota contabilizada debe tener un comprobante vinculado.'))
            if line.move_id and line.move_id.purchase_contract_id != line.contract_id:
                raise ValidationError(_('El comprobante pertenece a otro contrato.'))

    def unlink(self):
        if self.filtered(lambda line: line.move_id or line.payment_ids):
            raise UserError(_("No se puede eliminar una cuota con comprobantes o pagos."))
        return super().unlink()


class Move(models.Model):
    _inherit = 'account.move'
    purchase_contract_id = fields.Many2one('step.management.purchase.contract', string='Contrato de compra',
                                           check_company=True, copy=False, ondelete='restrict')


class Payment(models.Model):
    _inherit = 'account.payment'
    purchase_contract_installment_id = fields.Many2one('step.management.purchase.contract.installment',
        string='Cuota de contrato', check_company=True, copy=False, ondelete='restrict')

    @api.constrains('purchase_contract_installment_id','partner_id','company_id','currency_id','payment_type','partner_type','amount','state')
    def _check_contract_payment(self):
        for payment in self.filtered('purchase_contract_installment_id'):
            line = payment.purchase_contract_installment_id
            self.env.cr.execute('SELECT id FROM step_management_purchase_contract_installment WHERE id = %s FOR UPDATE', [line.id])
            line.invalidate_recordset(['payment_ids', 'amount_paid', 'amount_pending'])
            contract = line.contract_id
            if (payment.partner_id != contract.partner_id or payment.currency_id != contract.currency_id
                    or payment.payment_type != 'outbound' or payment.partner_type != 'supplier'):
                raise ValidationError(_("El pago debe ser de salida al proveedor y en la moneda del contrato."))
            if not line.active or line.reversal_move_id or line.state != 'posted':
                raise ValidationError(_("Seleccione una cuota activa y contabilizada, sin reversa."))
            if line.currency_id.compare_amounts(line.amount_paid, line.amount) > 0:
                raise ValidationError(_("Los pagos superan el importe de la cuota."))

    def write(self, vals):
        if 'purchase_contract_installment_id' in vals and self.filtered(lambda payment: payment.state not in ('draft', 'canceled', 'rejected')):
            raise UserError(_("No se puede reasignar la cuota de un pago ya procesado."))
        return super().write(vals)
