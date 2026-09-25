from odoo import _, models
from odoo.exceptions import UserError


class Cashflow(models.Model):
    _inherit = 'step.cashflow'

    def _collect_purchase_order(self):
        results = super()._collect_purchase_order()
        self.ensure_one()
        lines = self.env['step.management.purchase.contract.installment'].search([
            ('company_id', '=', self.company_id.id), ('contract_id.state', '=', 'confirmed'),
            ('state', 'in', ['approved', 'posted']), ('active', '=', True),
            ('reversal_move_id', '=', False)])
        pending = lines.filtered(lambda line: not line.currency_id.is_zero(line.amount_pending))
        concept = self.env['step.treasury.concept'].search([
            ('company_id', '=', self.company_id.id), ('code', '=', '22')], limit=1)
        if pending and (not concept or concept.flow_type != 'outflow'):
            raise UserError(_("Configure el concepto 22 de egreso para proyectar los contratos."))
        for line in pending:
            contract = line.contract_id
            results.append(dict(self._line_defaults('purchase_order'), **{
                'concept_id': concept.id, 'source_model': contract._name,
                'source_id': contract.id, 'source_line_id': line.id,
                'partner_id': contract.partner_id.id, 'partner_vat': contract.partner_id.vat or '',
                'doc_type_name': _('Cuota de contrato'),
                'doc_number': '%s / %s' % (contract.name, line.sequence),
                'doc_date': contract.date_start or contract.accounting_date,
                'due_date': line.date_due, 'currency_id': line.currency_id.id,
                'amount_origin': line.amount_pending}))
        return results
