from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


def preserve_original_batch_state(records):
    if records:
        raise UserError(_('Preserve original payroll batch states before removing their provider.'))


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    state = fields.Selection(selection_add=[('verify', 'To verify'), ('paid', 'Paid')],
                             ondelete={'verify': preserve_original_batch_state, 'paid': preserve_original_batch_state})
    move_id = fields.Many2one('account.move', readonly=True, copy=False, ondelete='set null')
    payslip_count = fields.Integer(compute='_compute_sys_payslip_count')

    @api.depends('slip_ids')
    def _compute_sys_payslip_count(self):
        for batch in self:
            batch.payslip_count = len(batch.slip_ids)

    def _step_sys_batch_members(self):
        self.ensure_one()
        self.check_access('write')
        self.check_field_access_rights('read', ['state', 'company_id', 'slip_ids', 'date_start', 'date_end'])
        if self.company_id != self.env.company:
            raise UserError(_('Select the batch company before processing payroll.'))
        self.flush_recordset()
        self.env.cr.execute('SELECT id FROM hr_payslip_run WHERE id=%s FOR UPDATE', [self.id])
        slips = self.env['hr.payslip']
        slips.flush_model(['payslip_run_id', 'state'])
        self.env.cr.execute('SELECT id FROM hr_payslip WHERE payslip_run_id=%s ORDER BY id FOR UPDATE', [self.id])
        members = slips.browse([row[0] for row in self.env.cr.fetchall()])
        members.check_access('write')
        members.check_field_access_rights('read', ['company_id','date_from','date_to','credit_note','state','move_id'])
        if any(s.company_id != self.company_id or s.date_from != self.date_start or s.date_to != self.date_end
               or s.credit_note for s in members):
            raise UserError(_('Every payslip must belong to the original company and payroll period.'))
        return members

    def _step_sys_mark_reviewable(self):
        for batch in self.filtered(lambda b: b.state == 'draft'):
            members = batch._step_sys_batch_members()
            if members and all(s.state == 'verify' for s in members):
                batch.write({'state':'verify'})

    def action_confirm(self):
        self.ensure_one()
        with self.env.cr.savepoint():
            members = self._step_sys_batch_members()
            if self.state not in ('draft', 'verify') or not members or any(s.state != 'verify' for s in members):
                raise UserError(_('Calculate every payslip in the batch before confirming it.'))
            if self.state == 'draft':
                self.write({'state':'verify'})

    def action_validate(self):
        self.ensure_one()
        with self.env.cr.savepoint():
            members = self._step_sys_batch_members()
            if self.state == 'close' and members and all(s.state == 'done' and s.move_id for s in members):
                return
            structure = self.env.ref('l10n_cl_simpledigital_payroll.structure_chile')
            if (self.company_id.id != 37 or self.state != 'verify' or not members
                    or any(s.state != 'verify' or s.move_id or not s.line_ids or s.struct_id != structure for s in members)):
                raise UserError(_('The original batch and every payslip must be ready for validation.'))
            members.with_context(without_compute_sheet=True).action_payslip_done()
            if not all(s.move_id and s.state == 'done' for s in members):
                raise UserError(_('One or more validated payslips has no accounting entry.'))
            self.write({'state':'close'})

    # SyS did not store the journal on its historical batches.
    journal_id = fields.Many2one(
        required=False,
        default=None,
        ondelete="restrict",
        check_company=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        with self.env.cr.savepoint():
            batches = super().create(vals_list)
            if any(not batch.journal_id for batch in batches):
                raise ValidationError(_("Select a salary journal for the new payroll batch."))
        return batches

    def write(self, vals):
        if self and "journal_id" in vals and not vals["journal_id"]:
            raise ValidationError(_("The salary journal cannot be cleared."))
        return super().write(vals)

    @api.constrains("journal_id", "company_id")
    def _check_salary_journal_company(self):
        self._check_company(["journal_id"])
