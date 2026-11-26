"""Preserve the draft accounting link of the original Cerro salary structure."""
from odoo import models
from odoo.tools import format_date


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def action_payslip_done(self):
        original = self.env.ref('hr_payroll.structure_002', raise_if_not_found=False)
        if len(self) != 1 or not original or self.struct_id != original:
            return super().action_payslip_done()

        with self.env.cr.savepoint():
            result = super().action_payslip_done()
            if self.state != 'done' or self.move_id:
                return result
            rules = self._get_salary_rules()
            rules.check_field_access_rights('read', ['account_debit', 'account_credit'])
            if rules and not (rules.account_debit or rules.account_credit):
                # The original engine leaves a linked empty draft when the
                # configured salary journal has no mapped rules. The normal
                # accounting ACL applies and no entry is posted.
                date = self.date or self.date_to
                move = self.env['account.move'].create({
                    'move_type': 'entry',
                    'journal_id': self.journal_id.id,
                    'date': date,
                    'ref': format_date(self.env, date, date_format='MMMM y',
                                       lang_code=self.env.user.lang),
                })
                self.move_id = move
            return result
