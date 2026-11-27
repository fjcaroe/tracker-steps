from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from .rule_configuration import CONFIRMED_COMPANIES


def preserve_original_batch_state(records):
    if records:
        raise UserError(_('Preserve original payroll batch states before removing their provider.'))


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    state = fields.Selection(selection_add=[('verify', 'To verify'), ('paid', 'Paid')],
                             ondelete={'verify': preserve_original_batch_state, 'paid': preserve_original_batch_state})
    move_id = fields.Many2one('account.move', readonly=True, copy=False, ondelete='set null')
    move_state = fields.Selection(related='move_id.state')
    company_id = fields.Many2one(readonly=True, copy=True)
    payslip_count = fields.Integer(compute='_compute_sys_payslip_count')
    country_id = fields.Many2one(related='company_id.country_id')
    country_code = fields.Char(related='country_id.code')
    payment_report = fields.Binary(readonly=True, attachment=True)
    payment_report_date = fields.Date(readonly=True)
    payment_report_filename = fields.Char(readonly=True)

    @api.depends('slip_ids')
    def _compute_sys_payslip_count(self):
        for batch in self:
            batch.payslip_count = len(batch.slip_ids)

    def _step_sys_batch_members(self):
        self.ensure_one()
        self.check_access('write')
        self.check_field_access_rights('read', ['state', 'company_id', 'slip_ids', 'date_start', 'date_end'])
        self.flush_recordset()
        self.env.cr.execute('SELECT id FROM hr_payslip_run WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if self.company_id != self.env.company:
            raise UserError(_('Select the batch company before processing payroll.'))
        slips = self.env['hr.payslip']
        slips.flush_model(['payslip_run_id', 'state'])
        self.env.cr.execute('SELECT id FROM hr_payslip WHERE payslip_run_id=%s ORDER BY id FOR UPDATE', [self.id])
        members = slips.browse([row[0] for row in self.env.cr.fetchall()])
        members.invalidate_recordset()
        members.check_access('write')
        members.check_field_access_rights('read', ['company_id','date_from','date_to','credit_note','state','move_id'])
        if any(s.company_id != self.company_id or s.date_from != self.date_start or s.date_to != self.date_end
               or s.credit_note for s in members):
            raise UserError(_('Every payslip must belong to the original company and payroll period.'))
        return members

    def _step_sys_mark_reviewable(self):
        for batch in self.filtered(lambda b: b.state == 'draft'):
            members = batch._step_sys_batch_members()
            if members and not members.mapped('move_id') and all(s.state == 'verify' for s in members):
                batch.write({'state':'verify'})

    def action_confirm(self):
        self.ensure_one()
        with self.env.cr.savepoint():
            members = self._step_sys_batch_members()
            if self.state == 'draft' and members and all(s.state == 'draft' and s.step_history_locked for s in members):
                structure = self.env.ref('l10n_cl_simpledigital_payroll.structure_chile')
                if (self.company_id.id not in CONFIRMED_COMPANIES
                        or any(s.struct_id != structure or not s.line_ids or not s.move_id for s in members)):
                    raise UserError(_('Review the frozen payslips and their original accounting entries.'))
                self._step_sys_check_reopened_moves(members, structure)
                members.write({'state': 'verify'})
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
            if (self.company_id.id not in CONFIRMED_COMPANIES or self.state != 'verify' or not members
                    or any(s.state != 'verify' or not s.line_ids or s.struct_id != structure for s in members)):
                raise UserError(_('The original batch and every payslip must be ready for validation.'))
            previous = {slip.id: slip.move_id for slip in members if slip.move_id}
            if previous:
                self._step_sys_check_reopened_moves(members, structure)
                if not all(s.step_history_locked for s in members):
                    raise UserError(_('Review the frozen payslips and their original accounting entries.'))
                members.write({'state': 'done'})
            else:
                members.with_context(without_compute_sheet=True).action_payslip_done()
            if not all(s.move_id and s.state == 'done' for s in members):
                raise UserError(_('One or more validated payslips has no accounting entry.'))
            if any(slip.move_id != previous[slip.id] for slip in members if slip.id in previous):
                raise UserError(_('The accounting entry of a reopened payslip changed.'))
            self.write({'state':'close'})

    def _step_sys_check_reopened_moves(self, members, structure):
        moves = members.mapped('move_id')
        moves.check_access('read')
        moves.check_field_access_rights('read', ['state', 'move_type', 'line_ids', 'company_id', 'journal_id', 'date'])
        moves.flush_recordset()
        self.env.cr.execute('SELECT id FROM account_move WHERE id=ANY(%s) ORDER BY id FOR UPDATE', [moves.ids])
        moves.invalidate_recordset()
        members.flush_model(['move_id'])
        self.env['account.move.line'].flush_model(['move_id'])
        self.env.cr.execute('SELECT EXISTS(SELECT FROM account_move_line WHERE move_id=ANY(%s)) '
                            'OR EXISTS(SELECT FROM hr_payslip WHERE move_id=ANY(%s) AND NOT (id=ANY(%s)))',
                            [moves.ids, moves.ids, members.ids])
        conflicting_entry, = self.env.cr.fetchone()
        rules = structure._step_effective_rule_scope()['rules']
        rules.check_access('read')
        rules.check_field_access_rights('read', ['account_debit', 'account_credit'])
        if (conflicting_entry or len(moves) != len(members) or rules.mapped('account_debit') or rules.mapped('account_credit')
                or any(s.move_id.state != 'draft' or s.move_id.move_type != 'entry'
                       or s.move_id.company_id != s.company_id or s.move_id.journal_id != s.journal_id
                       or s.move_id.date != (s.date or s.date_to) for s in members)):
            raise UserError(_('Review the existing journal entries before closing this reopened batch.'))

    def close_payslip_run(self):
        with self.env.cr.savepoint():
            for batch in self:
                batch.action_validate()
        return True

    def action_open_payslips(self):
        self.ensure_one()
        self.check_access('read')
        self.check_field_access_rights('read', ['slip_ids'])
        return {'type': 'ir.actions.act_window', 'name': _('Payslips'), 'res_model': 'hr.payslip',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('id', 'in', self.slip_ids.ids)],
                'context': dict(self.env.context, default_payslip_run_id=self.id)}

    def action_open_move(self):
        self.ensure_one()
        self.check_access('read')
        self.check_field_access_rights('read', ['move_id'])
        move = self.move_id
        if not move:
            raise UserError(_('This batch has no accounting entry.'))
        move.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': _('Journal Entry'), 'res_model': 'account.move',
                'views': [(False, 'form')], 'res_id': move.id}

    def _step_sys_change_batch_state(self, transitions, target, member_state):
        self.ensure_one()
        with self.env.cr.savepoint():
            members = self._step_sys_batch_members()
            if (self.company_id.id not in CONFIRMED_COMPANIES or self.state not in transitions
                    or not members or any(s.state not in transitions[self.state] for s in members)):
                raise UserError(_('The batch and its payslips must be in the expected state.'))
            members.filtered(lambda s: s.state != member_state).write({'state': member_state})
            self.write({'state': target})

    def action_paid(self):
        self._step_sys_change_batch_state({'close': ('done', 'paid')}, 'paid', 'paid')

    def action_unpaid(self):
        self._step_sys_change_batch_state({'paid': ('paid', 'done')}, 'close', 'done')

    def action_draft(self):
        self._step_sys_change_batch_state({'close': ('done',), 'verify': ('verify',)}, 'draft', 'draft')

    def draft_payslip_run(self):
        with self.env.cr.savepoint():
            for batch in self:
                batch.action_draft()
        return True

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
            # The original batch form has no journal selector. For a new SyS
            # batch, use the same explicit company property as its payslips.
            # A field default here would also initialize historical SQL rows.
            company = self.env.company
            if company.id in CONFIRMED_COMPANIES and not self.env.context.get('default_journal_id'):
                pending = [i for i, values in enumerate(vals_list)
                           if 'journal_id' not in values and values.get('company_id', company.id) == company.id]
                if pending:
                    structure = self.env.ref('l10n_cl_simpledigital_payroll.structure_chile')
                    structure.check_access('read')
                    structure.check_field_access_rights('read', ['journal_id'])
                    journal = structure.journal_id
                    journal.check_access('read')
                    journal.check_field_access_rights('read', ['company_id', 'type'])
                    structure.flush_recordset(['journal_id'])
                    self.env.cr.execute('SELECT journal_id->>%s FROM hr_payroll_structure WHERE id=%s',
                                        [str(company.id), structure.id])
                    configured, = self.env.cr.fetchone()
                    if journal and configured == str(journal.id) and journal.company_id == company and journal.type == 'general':
                        vals_list = list(vals_list)
                        for index in pending:
                            vals_list[index] = dict(vals_list[index], journal_id=journal.id)
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
