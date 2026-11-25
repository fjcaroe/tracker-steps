"""Cerro's observed hourly proration for its monthly structure 002."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.step_simpledigital_oca_base.models.original_unpaid import PAYMENT_DEPENDENCIES


class WorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    amount = fields.Monetary(depends=(*PAYMENT_DEPENDENCIES,
        'contract_id.schedule_pay', 'payslip_id.company_id.currency_id.rounding',
        'payslip_id.worked_days_line_ids.number_of_hours'))

    def _step_paid_worked_day_amount(self):
        self.ensure_one()
        original = self.env.ref('hr_payroll.structure_002', raise_if_not_found=False)
        if not original or self.payslip_id.struct_id != original:
            return super()._step_paid_worked_day_amount()

        normal = api.Environment(self.env.cr, self.env.uid, dict(self.env.context), su=False)
        line = self.with_env(normal)
        slip = line.payslip_id
        if line.contract_id.schedule_pay != 'monthly':
            raise UserError(_('The original hourly proration requires a monthly contract.'))
        # Resolve every sibling identity, then read hours only with the actor's
        # permissions. Omitting an inaccessible line would change the salary.
        siblings = slip.sudo().with_context(active_test=False).worked_days_line_ids.with_env(normal)
        siblings.check_access('read')
        siblings.check_field_access_rights('read', ['number_of_hours'])
        hours = sum(siblings.mapped('number_of_hours'))
        if not hours:
            return 0.0
        return slip.company_id.currency_id.round(line.contract_id.wage * line.number_of_hours / hours)
