"""Read-only reports over native accounting records, with historical cutoffs.

No sudo, SQL, cached business totals or substitute accounting tables. Company
currency is authoritative. Operational columns use stored historical amounts.
"""
import base64
import csv
import io
from collections import defaultdict

from markupsafe import Markup, escape
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

KINDS = [('bank', 'Conciliación bancaria'), ('ledger', 'Cuentas corrientes'),
         ('cash', 'Estado de flujo de efectivo'), ('receivable', 'Cuentas por cobrar vencidas'),
         ('payable', 'Cuentas por pagar vencidas')]


class TreasuryReport(models.TransientModel):
    _name = 'step.treasury.report'
    _description = 'Informe contable de Tesorería'
    _check_company_auto = True

    kind = fields.Selection(KINDS, required=True, default='ledger', string='Informe')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1), string='Desde')
    date_to = fields.Date(required=True, default=fields.Date.context_today, string='Al')
    partner_ids = fields.Many2many('res.partner', relation='step_treasury_report_partner_rel', string='Socios')
    journal_ids = fields.Many2many('account.journal', relation='step_treasury_report_journal_rel', string='Diarios', check_company=True)
    result_html = fields.Html(string='Resultado', readonly=True, sanitize=True)
    export_file = fields.Binary(readonly=True, attachment=False)
    export_name = fields.Char(readonly=True)

    def _scope(self):
        self.ensure_one()
        if not (self.env.user.has_group('account.group_account_readonly') or
                self.env.user.has_group('account.group_account_manager')):
            raise AccessError(_('Se requiere acceso contable de consulta.'))
        if self.company_id not in self.env.companies:
            raise AccessError(_('La empresa no está autorizada en la sesión.'))
        from ..hooks import LAUNCHERS
        menu_name = next(name for name, kind, *_ in LAUNCHERS if kind == self.kind)
        menu = self.env.ref('step_account_treasury.' + menu_name)
        if menu.id not in self.env['ir.ui.menu']._visible_menu_ids():
            raise AccessError(_('El perfil no permite este acceso de Tesorería.'))
        if not self.date_to or (self.kind not in ('receivable', 'payable') and (not self.date_from or self.date_from > self.date_to)):
            raise ValidationError(_('El período del informe no es válido.'))
        if any(j.company_id != self.company_id for j in self.journal_ids):
            raise AccessError(_('Los diarios deben pertenecer a la empresa del informe.'))
        domain = [('company_id', '=', self.company_id.id), ('parent_state', '=', 'posted'),
                  ('date', '<=', self.date_to)]
        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
        return domain

    def _lines(self, domain):
        return self.env['account.move.line'].with_company(self.company_id).search(
            domain, order='date,move_id,id')

    def _historical_residuals(self, lines):
        """Reverse matches after cutoff, even if a document is reconciled today.

        Restrict both endpoints to the company. ORM applies the user's record
        rules to partial reconciliations too. No current residual shortcut.
        """
        residuals = {line.id: line.balance for line in lines}
        if not lines:
            return residuals
        matches = self.env['account.partial.reconcile'].search([
            ('debit_move_id.company_id', '=', self.company_id.id),
            ('credit_move_id.company_id', '=', self.company_id.id),
            ('debit_move_id.date', '<=', self.date_to), ('credit_move_id.date', '<=', self.date_to),
            '|', ('debit_move_id', 'in', lines.ids), ('credit_move_id', 'in', lines.ids),
        ])
        for match in matches:
            if match.debit_move_id.id in residuals:
                residuals[match.debit_move_id.id] -= match.amount
            if match.credit_move_id.id in residuals:
                residuals[match.credit_move_id.id] += match.amount
        return residuals

    def _row(self, line, amount=None):
        return {'id': line.id, 'date': str(line.date), 'document': line.move_id.name,
                'partner': line.partner_id.display_name or '', 'account': line.account_id.display_name,
                'debit': line.debit, 'credit': line.credit,
                'balance': line.balance if amount is None else amount,
                'operational': line.operational_balance,
                'operational_currency': line.operational_currency_id.name or '',
                'currency': line.currency_id.name or '', 'amount_currency': line.amount_currency}

    def report_data(self):
        domain = self._scope()
        currency = self.company_id.currency_id
        result = {'kind': self.kind, 'title': dict(KINDS)[self.kind], 'currency': currency.name,
                  'opening': 0.0, 'movement': 0.0, 'closing': 0.0, 'rows': [], 'buckets': {},
                  'notice': ''}
        if self.kind in ('receivable', 'payable'):
            account_type = 'asset_receivable' if self.kind == 'receivable' else 'liability_payable'
            lines = self._lines(domain + [('account_id.account_type', '=', account_type)])
            residuals = self._historical_residuals(lines)
            totals = defaultdict(float)
            for line in lines:
                residual = residuals[line.id]
                if currency.is_zero(residual):
                    continue
                days = (self.date_to - (line.date_maturity or line.date)).days
                band = 'No vencido' if days <= 0 else '1–30' if days <= 30 else '31–60' if days <= 60 else '61–90' if days <= 90 else '91–120' if days <= 120 else '>120'
                row = self._row(line, residual)
                row.update(due=str(line.date_maturity or line.date), bucket=band,
                           # Invoice-date historical valuation, not a settlement FX result.
                           operational=(line.operational_balance * residual / line.balance if line.balance else 0.0))
                result['rows'].append(row)
                totals[band] += residual
            result['buckets'] = dict(totals)
            result['closing'] = sum(residuals.values())
            result['notice'] = 'Saldo firmado al corte; proveedores acreedores son negativos. Incluye documentos hoy conciliados si estaban abiertos al corte. Operacional residual valorado a la tasa histórica de cada apunte, sin recalcular diferencias de cambio.'
        else:
            if self.kind == 'ledger':
                domain += [('account_id.account_type', 'in', ('asset_receivable', 'liability_payable'))]
            else:
                domain += [('account_id.account_type', '=', 'asset_cash')]
            lines = self._lines(domain)
            result['opening'] = sum(line.balance for line in lines if line.date < self.date_from)
            current = lines.filtered(lambda line: line.date >= self.date_from)
            result['rows'] = [self._row(line) for line in current]
            result['movement'] = sum(current.mapped('balance'))
            result['closing'] = result['opening'] + result['movement']
            grouped = defaultdict(lambda: {'opening': 0.0, 'movement': 0.0, 'closing': 0.0})
            for line in lines:
                key = line.partner_id.display_name or _('Sin socio') if self.kind == 'ledger' else line.account_id.display_name
                # IDs, rather than names, distinguish homonymous partners/accounts.
                identity = line.partner_id.id if self.kind == 'ledger' else line.account_id.id
                group = grouped[identity]
                group['label'] = key
                group['opening' if line.date < self.date_from else 'movement'] += line.balance
                group['closing'] += line.balance
            result['summary'] = list(grouped.values())
            running = result['opening']
            for row in result['rows']:
                running += row['balance']
                row['running'] = running
            if self.kind == 'cash':
                result['notice'] = 'Efectivo realizado: saldo inicial + apuntes publicados de cuentas de efectivo = saldo final. Las transferencias internas se compensan al incluir ambos bancos. No es una proyección ni una clasificación normativa de actividades. Las columnas operacionales conservan los valores históricos por moneda y no se suman entre monedas.'
            elif self.kind == 'bank':
                self._bank_data(result, domain)
        return result

    def _bank_data(self, result, liquidity_domain):
        # Reconciliation control reports statement evidence and outstanding
        # ledger items; posting or reconciling remains a native accounting flow.
        statement_domain = [('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
                            ('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        if self.journal_ids:
            statement_domain.append(('journal_id', 'in', self.journal_ids.ids))
        if self.partner_ids:
            statement_domain.append(('partner_id', 'in', self.partner_ids.ids))
        statements = self.env['account.bank.statement.line'].search(statement_domain, order='date,id')
        result['statements'] = [{'id': row.id, 'date': str(row.date), 'label': row.payment_ref,
                                 'amount': row.amount, 'currency': (row.journal_id.currency_id or self.company_id.currency_id).name,
                                 'reconciled_now': row.is_reconciled} for row in statements]
        outstanding = self._lines(self._scope() + [('account_id.reconcile', '=', True),
                                  ('journal_id.type', 'in', ('bank', 'cash'))])
        remaining = self._historical_residuals(outstanding)
        result['outstanding'] = [self._row(row, remaining[row.id]) for row in outstanding
                                 if not self.company_id.currency_id.is_zero(remaining[row.id])]
        anchors = []
        journals = self.journal_ids or self.env['account.journal'].search([
            ('company_id', '=', self.company_id.id), ('type', 'in', ('bank', 'cash'))])
        for journal in journals:
            candidates = self.env['account.bank.statement'].search([
                ('journal_id', '=', journal.id), ('date', '<=', self.date_to)], order='first_line_index desc')
            anchor = candidates.filtered(lambda s: s.line_ids and max(s.line_ids.mapped('date')) <= self.date_to)[:1]
            if not anchor or self.partner_ids:
                continue  # A partial partner filter cannot reconcile a whole bank balance.
            cutoff = max(anchor.line_ids.mapped('date'))
            ledger = self._lines([('company_id', '=', self.company_id.id), ('parent_state', '=', 'posted'),
                                  ('account_id', '=', journal.default_account_id.id), ('date', '<=', cutoff)])
            money = journal.currency_id or self.company_id.currency_id
            if money != self.company_id.currency_id and any(line.currency_id != money for line in ledger):
                continue  # No meaningful comparison exists for mixed document currencies.
            ledger_balance = sum(ledger.mapped('amount_currency' if money != self.company_id.currency_id else 'balance'))
            anchors.append({'label': journal.display_name, 'date': str(cutoff), 'currency': money.name,
                            'statement': anchor.balance_end_real, 'ledger': ledger_balance,
                            'difference': anchor.balance_end_real - ledger_balance})
        result['anchors'] = anchors
        result['notice'] = 'Control de conciliación: libro de efectivo al corte, extractos del período y partidas conciliables pendientes al corte. El estado del extracto es el estado actual, indicado expresamente; no reconstruye cambios históricos del indicador. Los importes de extracto están separados por moneda. Abrir los documentos para completar la conciliación nativa.'

    def _html_table(self, rows, columns, model='account.move.line'):
        heading = Markup('').join(Markup('<th>%s</th>') % label for key, label in columns)
        body = []
        for row in rows:
            cells = []
            for key, label in columns:
                value = row.get(key, '')
                if isinstance(value, float):
                    value = '%.2f' % value
                cells.append(Markup('<td>%s</td>') % value)
            if row.get('id'):
                cells.append(Markup('<td><a href="/web#model=%s&amp;id=%s&amp;view_type=form" target="_blank">Abrir</a></td>') % (model, row['id']))
            body.append(Markup('<tr>%s</tr>') % Markup('').join(cells))
        return Markup('<table class="table table-sm table-striped"><thead><tr>%s<th>Documento</th></tr></thead><tbody>%s</tbody></table>') % (heading, Markup('').join(body))

    def action_calculate(self):
        data = self.report_data()
        columns = [('date', 'Fecha'), ('document', 'Asiento'), ('partner', 'Socio'), ('account', 'Cuenta'),
                   ('debit', 'Debe'), ('credit', 'Haber'), ('balance', 'Saldo / movimiento'),
                   ('currency', 'Moneda documento'), ('amount_currency', 'Importe documento'),
                   ('operational_currency', 'Moneda operacional'), ('operational', 'Importe operacional')]
        if self.kind in ('receivable', 'payable'):
            columns += [('due', 'Vencimiento'), ('bucket', 'Antigüedad')]
        else:
            columns += [('running', 'Acumulado')]
        html = Markup('<h2>%s</h2><p>%s — %s / %s</p><p>%s</p><p>Inicial: %.2f | Movimiento: %.2f | Final: %.2f (%s)</p>') % (
            data['title'], self.company_id.name, self.date_from if self.kind not in ('receivable', 'payable') else _('Corte'), self.date_to, data['notice'],
            data['opening'], data['movement'], data['closing'], data['currency'])
        html += Markup('<p>Socios: %s | Diarios: %s</p>') % (
            ', '.join(self.partner_ids.mapped('display_name')) or _('Todos'),
            ', '.join(self.journal_ids.mapped('display_name')) or _('Todos'))
        if data['buckets']:
            html += self._html_table([{'bucket': key, 'balance': value} for key, value in data['buckets'].items()], [('bucket', 'Antigüedad'), ('balance', 'Saldo')])
        if data.get('summary'):
            html += self._html_table(data['summary'], [('label', 'Socio / cuenta'), ('opening', 'Inicial'), ('movement', 'Movimiento'), ('closing', 'Final')])
        html += self._html_table(data['rows'], columns)
        if self.kind == 'bank':
            html += Markup('<h3>Saldos de extracto frente a libro en fecha de último extracto completo</h3>')
            html += self._html_table(data['anchors'], [('label', 'Banco'), ('date', 'Fecha'), ('currency', 'Moneda'), ('statement', 'Extracto'), ('ledger', 'Libro'), ('difference', 'Diferencia')])
            html += Markup('<h3>Extractos (estado actual)</h3>')
            html += self._html_table(data['statements'], [('date', 'Fecha'), ('label', 'Referencia'), ('amount', 'Importe'), ('currency', 'Moneda'), ('reconciled_now', 'Conciliado actualmente')], 'account.bank.statement.line')
            html += Markup('<h3>Partidas pendientes al corte</h3>') + self._html_table(data['outstanding'], columns[:-1])
        self.result_html = html
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'current'}

    def action_export(self):
        """Same canonical dataset, including summary and bank evidence sections."""
        data = self.report_data()
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        def safe(value):
            value = str(value)
            return "'" + value if value.startswith(('=', '+', '-', '@')) else value
        writer.writerow([data['title'], self.company_id.name, str(self.date_from), str(self.date_to), data['currency']])
        writer.writerow(['Socios', safe(', '.join(self.partner_ids.mapped('display_name')) or 'Todos'),
                         'Diarios', safe(', '.join(self.journal_ids.mapped('display_name')) or 'Todos')])
        writer.writerow(['Inicial', data['opening'], 'Movimiento', data['movement'], 'Final', data['closing']])
        writer.writerow([data['notice']])
        for label in ('summary', 'rows', 'anchors', 'statements', 'outstanding'):
            rows = data.get(label, [])
            writer.writerow([label])
            if rows:
                keys = list(rows[0])
                writer.writerow(keys)
                for row in rows:
                    writer.writerow([row[key] if isinstance(row[key], (float, int)) else safe(row[key]) for key in keys])
        self.export_file = base64.b64encode(stream.getvalue().encode('utf-8-sig'))
        self.export_name = 'tesoreria-%s-%s.csv' % (self.kind, self.date_to)
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s/%s/export_file/%s?download=true' % (self._name, self.id, self.export_name), 'target': 'self'}

    def action_print(self):
        self.action_calculate()
        return self.env.ref('step_treasury_community_reports.report_print').report_action(self, config=False)
