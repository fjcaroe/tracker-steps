"""Apply new manual drafts to their saved invoice links using real account APIs.

This reconciles the receivable/payable counterpart, never a bank statement or
native batch workflow. Provider-calculated paid/in_payment labels are retained.
"""
import math

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL

from .posting_service import BATCH_FIELDS, PAYMENT_FIELDS


INVOICE_FIELDS = ['state', 'move_type', 'company_id', 'currency_id', 'partner_id',
                  'payment_state', 'amount_residual', 'amount_total', 'line_ids']
LINE_FIELDS = ['move_id', 'company_id', 'currency_id', 'partner_id', 'account_id',
               'balance', 'amount_currency', 'amount_residual', 'amount_residual_currency',
               'matched_debit_ids', 'matched_credit_ids', 'reconciled', 'full_reconcile_id']
LINE_FIELDS.append('statement_line_id')
IMMUTABLE_LINE_FIELDS = ['id', 'move_id', 'date', 'company_id', 'currency_id',
                         'partner_id', 'account_id', 'balance', 'amount_currency', 'debit', 'credit']


class BatchPaymentInvoiceApplication(models.AbstractModel):
    _inherit = 'step.batch.payment.grouping'

    @api.model
    def post_groups_against_linked_invoices(self, batch_ids):
        return self._application_entry(batch_ids)

    @api.model
    def post_groups_against_invoices(self, batch_ids, allocations):
        """Explicit [[payment_id, invoice_id], ...] must match all saved links."""
        if not isinstance(allocations, (list, tuple)) or not allocations:
            raise UserError(_('Seleccione las relaciones guardadas de todos los pagos.'))
        mapping = {}
        for pair in allocations:
            if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                    or any(type(value) is not int or value <= 0 for value in pair)
                    or pair[0] in mapping):
                raise UserError(_('Cada pago debe indicar un único documento existente, sin repeticiones.'))
            mapping[pair[0]] = pair[1]
        return self._application_entry(batch_ids, mapping)

    @api.model
    def _application_entry(self, batch_ids, mapping=None):
        # Do not inherit caller flags that suppress reconciliation/account checks
        # or inject accounting defaults. The actor remains the actual UID.
        context = {key: self.env.context[key] for key in ('allowed_company_ids', 'lang', 'tz')
                   if key in self.env.context}
        context.update(tracking_disable=True, mail_notrack=True, mail_create_nosubscribe=True,
                       mail_notify_force_send=False, mail_post_autofollow=False)
        normal = self.sudo(False).with_context(context)
        with normal.env.cr.savepoint():
            return normal._post_and_apply_saved_invoices(batch_ids, mapping)

    @api.model
    def _saved_invoice_links(self, payments):
        payments.check_access('read')
        payments.check_field_access_rights('read', ['invoice_ids'])
        self.env['account.move'].check_access('read')
        relation = payments._fields['invoice_ids']
        if relation.type != 'many2many' or relation.comodel_name != 'account.move' or not relation.store:
            raise UserError(_('La relación original de documentos del pago no está disponible.'))
        payments.flush_recordset(['invoice_ids'])
        self.env.cr.execute(SQL('SELECT %s,%s FROM %s WHERE %s=ANY(%s) ORDER BY %s,%s',
            SQL.identifier(relation.column1), SQL.identifier(relation.column2), SQL.identifier(relation.relation),
            SQL.identifier(relation.column1), payments.ids,
            SQL.identifier(relation.column1), SQL.identifier(relation.column2)))
        links = {ident: [] for ident in payments.ids}
        for payment_id, invoice_id in self.env.cr.fetchall():
            links[payment_id].append(invoice_id)
        if any(len(value) != 1 for value in links.values()):
            raise UserError(_('Guarde exactamente una factura o cuenta por pagar por cada pago antes de agrupar.'))
        mapping = {ident: values[0] for ident, values in links.items()}
        if len(set(mapping.values())) != len(mapping):
            raise UserError(_('Un documento no puede aplicarse desde varios pagos de esta operación.'))
        return mapping

    @api.model
    def _authorized_move_lines(self, moves):
        moves.check_access('read')
        moves.check_field_access_rights('read', ['line_ids'])
        line_model = self.env['account.move.line']
        line_model.check_access('read'); line_model.check_access('write')
        line_model.check_field_access_rights('read', LINE_FIELDS + IMMUTABLE_LINE_FIELDS)
        self.env['account.move.line'].flush_model(['move_id'])
        self.env.cr.execute('SELECT id FROM account_move_line WHERE move_id=ANY(%s) ORDER BY id', [moves.ids])
        lines = self.env['account.move.line'].browse([row[0] for row in self.env.cr.fetchall()])
        lines.check_access('read')
        lines.check_access('write')
        lines.check_field_access_rights('read', LINE_FIELDS + IMMUTABLE_LINE_FIELDS)
        return lines

    @api.model
    def _usable_application_account(self, account, expected_type=None):
        account.check_access('read')
        account.check_field_access_rights('read', ['code', 'deprecated', 'account_type', 'reconcile'])
        if (not account or account.deprecated or account.code == '210233'
                or account.account_type == 'asset_cash'
                or expected_type and (account.account_type != expected_type or not account.reconcile)):
            raise UserError(_('La aplicación requiere cuentas vigentes conciliables; no admite efectivo ni la cuenta 210233.'))

    @api.model
    def _post_and_apply_saved_invoices(self, batch_ids, mapping):
        ids = self._existing_payment_ids(batch_ids)
        batches = self._provider().browse(ids)
        batches.check_access('read'); batches.check_access('write')
        batches.check_field_access_rights('read', BATCH_FIELDS)
        extra = ['invoice_ids', 'destination_account_id', 'date', 'is_reconciled']
        self.env['account.payment'].check_field_access_rights('read', PAYMENT_FIELDS + extra)
        self.env['account.partial.reconcile'].check_access('create')
        self.env['account.partial.reconcile'].check_access('read')
        self.env['account.partial.reconcile'].check_field_access_rights('read', ['debit_move_id', 'credit_move_id'])
        for ident in ids:
            self._lock_batch(ident)
        selections = {batch.id: self._group_payment_ids(batch) for batch in batches}
        if any(not value for value in selections.values()):
            raise UserError(_('Todos los grupos deben contener pagos nuevos.'))
        payments = self._lock_payments(sorted({ident for value in selections.values() for ident in value}))
        if len(payments.company_id) != 1:
            raise UserError(_('Aplique documentos de una sola empresa por operación.'))
        company = payments.company_id
        if company not in self.env.companies:
            raise AccessError(_('La empresa del pago no está habilitada.'))
        service = self.with_context(allowed_company_ids=company.ids).with_company(company)
        payments = payments.with_env(service.env)
        batches = batches.with_env(service.env)
        company.check_field_access_rights('read', ['tax_exigibility', 'currency_id'])
        if company.tax_exigibility:
            raise UserError(_('El régimen de impuesto en base a caja requiere su admisión antes de aplicar estos pagos.'))
        payments.flush_recordset(PAYMENT_FIELDS + extra)
        payments.invalidate_recordset(PAYMENT_FIELDS + extra)
        payments.check_access('read'); payments.check_access('write')
        saved = service._saved_invoice_links(payments)
        if mapping is not None and mapping != saved:
            raise UserError(_('La selección debe coincidir exactamente con todos los documentos guardados en los pagos.'))
        invoices = service.env['account.move'].browse(sorted(saved.values()))
        invoices.check_access('read'); invoices.check_access('write')
        invoices.check_field_access_rights('read', INVOICE_FIELDS)
        invoices.flush_recordset(INVOICE_FIELDS)
        service.env.cr.execute('SELECT id FROM account_move WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [invoices.ids])
        if [row[0] for row in service.env.cr.fetchall()] != invoices.ids:
            raise UserError(_('Un documento seleccionado ya no existe.'))
        lines = service._authorized_move_lines(invoices)
        lines.flush_recordset(LINE_FIELDS)
        service.env.cr.execute('SELECT id FROM account_move_line WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [lines.ids])
        if [row[0] for row in service.env.cr.fetchall()] != lines.ids:
            raise UserError(_('Una línea del documento ya no existe.'))
        invoices.invalidate_recordset(INVOICE_FIELDS); lines.invalidate_recordset(LINE_FIELDS)
        invoices.check_access('read'); invoices.check_access('write')
        lines.check_access('read'); lines.check_access('write')
        lines.account_id.check_access('read')
        lines.account_id.check_field_access_rights('read', ['account_type'])
        payments.partner_id.check_access('read'); invoices.partner_id.check_access('read')
        service.env.cr.execute('SELECT id FROM account_partial_reconcile WHERE debit_move_id=ANY(%s) '
                               'OR credit_move_id=ANY(%s) ORDER BY id', [lines.ids, lines.ids])
        prior = service.env['account.partial.reconcile'].browse([row[0] for row in service.env.cr.fetchall()])
        prior.check_access('read')
        if prior:
            raise UserError(_('Los documentos con conciliaciones anteriores requieren su flujo propio.'))
        counterparts = {}
        for payment in payments:
            if (payment.state != 'draft' or payment.move_id or payment.is_sent or payment.is_matched
                    or payment.is_reconciled or not math.isfinite(payment.amount) or payment.amount <= 0):
                raise UserError(_('Sólo se aplican pagos nuevos en borrador sin asiento, envío o conciliación previos.'))
            invoice = invoices.browse(saved[payment.id])
            expected = {('outbound', 'supplier'): ('in_invoice', 'liability_payable', -1),
                        ('inbound', 'customer'): ('out_invoice', 'asset_receivable', 1)}.get(
                            (payment.payment_type, payment.partner_type))
            if not expected or invoice.move_type != expected[0] or invoice.state != 'posted':
                raise UserError(_('El tipo de factura y la dirección del pago no corresponden.'))
            if (invoice.company_id != company or payment.currency_id != company.currency_id
                    or invoice.currency_id != company.currency_id or invoice.partner_id != payment.partner_id):
                raise UserError(_('Documento y pago deben compartir empresa, tercero exacto y moneda de compañía; no se admite FX.'))
            if (invoice.payment_state != 'not_paid' or invoice.amount_residual <= 0
                    or invoice.amount_residual != invoice.amount_total or payment.amount != invoice.amount_residual):
                raise UserError(_('El documento debe estar totalmente abierto y su saldo debe coincidir exactamente con el pago.'))
            service._usable_application_account(payment.outstanding_account_id)
            service._usable_application_account(payment.destination_account_id, expected[1])
            if (payment.outstanding_account_id.account_type not in ('asset_current', 'liability_current')
                    or not payment.outstanding_account_id.reconcile
                    or payment.outstanding_account_id == payment.destination_account_id):
                raise UserError(_('La cuenta pendiente debe ser corriente, conciliable y distinta de la contraparte.'))
            candidates = lines.filtered(lambda line: line.move_id == invoice
                and line.account_id.account_type in ('asset_receivable', 'liability_payable'))
            if len(candidates) != 1:
                raise UserError(_('Esta aplicación requiere un único vencimiento contable por documento.'))
            line = candidates
            if (line.company_id != company or line.currency_id != company.currency_id
                    or line.partner_id != payment.partner_id or line.account_id != payment.destination_account_id
                    or line.reconciled or line.matched_debit_ids or line.matched_credit_ids
                    or line.amount_residual != line.balance or expected[2] * line.balance <= 0
                    or abs(line.amount_residual) != payment.amount):
                raise UserError(_('La contraparte real del documento no está abierta o no coincide con el pago.'))
            counterparts[payment.id] = line
        invoice_immutable = invoices.read(['id', 'name', 'date', 'invoice_date', 'move_type', 'state',
            'company_id', 'currency_id', 'partner_id', 'amount_total', 'amount_untaxed', 'amount_tax'])
        ledger_immutable = lines.read(IMMUTABLE_LINE_FIELDS)
        immutable_payment_fields = ['id', 'date', 'amount', 'company_id', 'currency_id', 'journal_id',
            'payment_type', 'partner_type', 'partner_id', 'partner_bank_id', 'payment_method_line_id',
            'outstanding_account_id', 'destination_account_id']
        payment_immutable = payments.read(immutable_payment_fields)
        result = service.post_groups_draft_payments(batches.ids)
        payments.write({'batch_payment_id': False})
        payment_ledger = service._authorized_move_lines(payments.move_id)
        posted_immutable = payment_ledger.read(IMMUTABLE_LINE_FIELDS)
        partial_ids = []
        for payment in payments:
            payment_lines = service._authorized_move_lines(payment.move_id)
            target = payment_lines.filtered(lambda line: line.account_id == payment.destination_account_id)
            if len(target) != 1:
                raise UserError(_('El asiento real del pago no devolvió una contraparte única.'))
            (target | counterparts[payment.id]).reconcile()
            target.invalidate_recordset(LINE_FIELDS)
            counterparts[payment.id].invalidate_recordset(LINE_FIELDS)
            if (target.amount_residual != 0 or target.amount_residual_currency != 0
                    or counterparts[payment.id].amount_residual != 0
                    or counterparts[payment.id].amount_residual_currency != 0):
                raise UserError(_('El proveedor no aplicó completamente las contrapartes.'))
            partial_ids.extend((target.matched_debit_ids | target.matched_credit_ids).ids)
        payments.flush_recordset(['state', 'is_matched', 'is_reconciled', 'is_sent'])
        payments.invalidate_recordset(['state', 'is_matched', 'is_reconciled', 'is_sent'])
        payment_ledger.invalidate_recordset(LINE_FIELDS)
        for payment in payments:
            pending = payment_ledger.filtered(lambda line: line.move_id == payment.move_id
                                              and line.account_id == payment.outstanding_account_id)
            signed = payment.amount if payment.payment_type == 'inbound' else -payment.amount
            if (len(pending) != 1 or pending.amount_residual != signed
                    or pending.amount_residual_currency != signed or pending.statement_line_id
                    or pending.reconciled or pending.full_reconcile_id):
                raise UserError(_('La cuenta pendiente real debe conservar todo su saldo sin conciliación bancaria.'))
            service.env.cr.execute('SELECT id FROM account_partial_reconcile WHERE debit_move_id=%s OR credit_move_id=%s',
                                   [pending.id, pending.id])
            unexpected = service.env['account.partial.reconcile'].browse([row[0] for row in service.env.cr.fetchall()])
            unexpected.check_access('read')
            if unexpected:
                raise UserError(_('La cuenta pendiente no debe tener aplicaciones o conciliaciones bancarias.'))
        for batch in batches:
            current = payments.browse(selections[batch.id])
            if any(payment.is_matched or payment.is_sent or not payment.is_reconciled for payment in current):
                raise UserError(_('La aplicación no debe ejecutar ni conciliar movimientos bancarios.'))
            current.write({'batch_payment_id': batch.id})
            batch.invalidate_recordset(['state', 'payment_ids'])
            if batch.state != 'draft' or service._group_payment_ids(batch) != selections[batch.id]:
                raise UserError(_('El proveedor no conservó el grupo en borrador con sus miembros originales.'))
            service._log_group_invoice_application(batch, current)
        if invoices.read(list(invoice_immutable[0])) != invoice_immutable or lines.read(IMMUTABLE_LINE_FIELDS) != ledger_immutable:
            raise UserError(_('La aplicación cambió importes, referencias o líneas contables originales.'))
        if payments.read(immutable_payment_fields) != payment_immutable or payment_ledger.read(IMMUTABLE_LINE_FIELDS) != posted_immutable:
            raise UserError(_('El proveedor cambió valores o asientos de los pagos nuevos.'))
        if any(invoice.amount_residual != 0 for invoice in invoices):
            raise UserError(_('Los documentos no quedaron completamente aplicados.'))
        if service._saved_invoice_links(payments) != saved:
            raise UserError(_('El proveedor cambió las relaciones originales de documentos.'))
        service.env['account.partial.reconcile'].browse(sorted(set(partial_ids))).check_access('read')
        result.update(invoice_ids=invoices.ids, partial_reconcile_ids=sorted(set(partial_ids)),
                      payment_states={payment.id: payment.state for payment in payments},
                      invoice_payment_states={invoice.id: invoice.payment_state for invoice in invoices})
        return result

    @api.model
    def _log_group_invoice_application(self, batch, payments):
        batch.with_context(mail_notify_force_send=False, mail_post_autofollow=False,
                           mail_create_nosubscribe=True).message_post(
            body=_('Se aplicaron %(count)s pagos nuevos a sus documentos guardados mediante contrapartes contables. '
                   'El grupo sigue en borrador, sin envío ni conciliación bancaria.', count=len(payments)),
            message_type='comment', subtype_xmlid='mail.mt_note', partner_ids=[])
