from markupsafe import Markup

from odoo import _, models
from odoo.addons.step_payroll_oca_api.models.payroll import CategoryMapping
from odoo.exceptions import UserError
from odoo.tools import format_date


CONFIRMED_COMPANIES = {2, 5, 6, 7, 8, 12, 13, 29, 32, 36, 37}

RULE_FIELDS = (
    'struct_id', 'sequence', 'category_id', 'code', 'quantity', 'condition_select', 'condition_range',
    'condition_range_min', 'condition_range_max', 'condition_python', 'amount_select', 'amount_fix',
    'amount_percentage_base', 'amount_percentage', 'amount_python_compute', 'condition_other_input_id',
    'amount_other_input_id', 'partner_id', 'not_computed_in_net', 'split_move_lines',
)


def calculation_fingerprint(cr, ids):
    # Hash the original rule records and all reachable category parents. No
    # formula or employee data leaves the database. Names and audit timestamps
    # do not participate in calculation.
    columns = ', '.join('r.' + field for field in ('id', *RULE_FIELDS))
    cr.execute(f"""
        WITH RECURSIVE selected AS (
            SELECT * FROM hr_salary_rule WHERE id = ANY(%s)
        ), categories AS (
            SELECT c.id,c.code,c.parent_id FROM hr_salary_rule_category c
             WHERE c.id IN (SELECT category_id FROM selected)
            UNION
            SELECT p.id,p.code,p.parent_id FROM categories c
              JOIN hr_salary_rule_category p ON p.id=c.parent_id
        )
        SELECT encode(sha256(convert_to(jsonb_build_array(
            (SELECT jsonb_agg(jsonb_build_array({columns}) ORDER BY r.sequence,r.id) FROM selected r),
            (SELECT jsonb_agg(jsonb_build_array(c.id,c.code,c.parent_id) ORDER BY c.id) FROM categories c)
        )::text, 'UTF8')), 'hex')
    """, [ids])
    return cr.fetchone()[0]


class SysCategoryMapping(CategoryMapping):
    def get(self, code, default=None):
        # The native SyS evaluator returns 0 for an absent category even when
        # the formula provides an explicit fallback. Keep populated zeroes.
        return self.dict.get(code, 0)


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_baselocaldict(self, contracts):
        values = super()._get_baselocaldict(contracts)
        values['categories'] = SysCategoryMapping(values['categories'].dict)
        return values

    def compute_sheet(self):
        with self.env.cr.savepoint():
            batches = self.mapped('payslip_run_id').filtered(lambda b: b.company_id.id == 37)
            if any(b.state in ('close','paid') for b in batches):
                raise UserError(_('The original payroll batch is closed.'))
            result = super().compute_sheet()
            batches._step_sys_mark_reviewable()
            return result

    def _step_sys_matches_closed_worked_days(self):
        """Recognize an exact, readable original attendance snapshot on a new draft."""
        self.ensure_one()
        if self.company_id.id not in CONFIRMED_COMPANIES or self.company_id != self.env.company:
            return False
        original = self.search([
            ('id', '!=', self.id), ('state', 'in', ('done', 'paid')),
            ('company_id', '=', self.company_id.id), ('employee_id', '=', self.employee_id.id),
            ('contract_id', '=', self.contract_id.id), ('struct_id', '=', self.struct_id.id),
            ('date_from', '=', self.date_from), ('date_to', '=', self.date_to),
            ('credit_note', '=', self.credit_note),
        ], limit=2)
        if len(original) != 1:
            return False
        days = self.env['hr.payslip.worked_days']
        fields = ['payslip_id', 'work_entry_type_id', 'number_of_days', 'number_of_hours']
        for slip in (original, self):
            slip.check_field_access_rights('read', ['worked_days_line_ids'])
        days.check_field_access_rights('read', fields)
        days.flush_model(fields)
        self.env.cr.execute(
            'SELECT id FROM hr_payslip_worked_days WHERE payslip_id IN (%s,%s)', [original.id, self.id])
        days.browse([row[0] for row in self.env.cr.fetchall()]).check_access('read')
        def snapshot(slip):
            return sorted((day.work_entry_type_id.id, day.number_of_days, day.number_of_hours)
                          for day in slip.worked_days_line_ids)
        actual = snapshot(self)
        return bool(actual and all(work_type and hours > 0 and count > 0 for work_type, count, hours in actual)
                    and actual == snapshot(original))

    def action_payslip_done(self):
        structure = self.env.ref('l10n_cl_simpledigital_payroll.structure_chile', raise_if_not_found=False)
        with self.env.cr.savepoint():
            result = super().action_payslip_done()
            for slip in self.filtered(lambda record: record.state == 'done' and not record.move_id):
                if slip.company_id.id not in CONFIRMED_COMPANIES or slip.struct_id != structure:
                    continue
                # SyS retains a draft accounting header even without any rule
                # accounts. The regular payroll provider handles mapped lines.
                if slip.credit_note or (slip.payslip_run_id and slip.company_id.id != 37):
                    raise UserError(_('The original accounting treatment of this batch or refund needs verification.'))
                rules = structure._step_effective_rule_scope()['rules']
                rules.check_access('read')
                rules.check_field_access_rights('read', ['account_debit', 'account_credit'])
                if rules.mapped('account_debit') or rules.mapped('account_credit'):
                    raise UserError(_('The configured salary accounts produced no accounting entry.'))
                date = slip.date or slip.date_to
                move = self.env['account.move'].create({
                    'move_type': 'entry', 'company_id': slip.company_id.id,
                    'journal_id': slip.journal_id.id, 'date': date,
                    'ref': format_date(slip.env, date, date_format='MMMM y'),
                    'narration': Markup('<p>%s</p><br>') % slip.number,
                })
                slip.write({'date': date, 'move_id': move.id})
            return result


class Structure(models.Model):
    _inherit = 'hr.payroll.structure'

    def _step_verified_rule_collisions(self, rules, duplicates):
        self.ensure_one()
        # The same two evaluation paths have been exercised in the native and
        # free engines both with and without an employee movement. Both rules
        # run under their own identities. This only describes which line the
        # engines retain after evaluation; it never filters the engine's rules.
        if (self.env.company.id not in CONFIRMED_COMPANIES or self.id != 4 or len(rules) != 67
                or duplicates != {'MOV_7': [67, 68], 'NET': [8, 32]}
                or self != self.env.ref('l10n_cl_simpledigital_payroll.structure_chile', raise_if_not_found=False)):
            return {}
        rules.check_access('read')
        rules.check_field_access_rights('read', list(RULE_FIELDS))
        rules.flush_recordset(list(RULE_FIELDS))
        categories = self.env['hr.salary.rule.category']
        categories.check_field_access_rights('read', ['parent_id','code'])
        categories.flush_model(['parent_id','code'])
        if calculation_fingerprint(self.env.cr, rules.ids) != '88a313b793d1f7ddc9c4c31f59158998ecc7a5dc478c988d886209fe32976582':
            return {}
        return {'MOV_7': 68, 'NET': 32}
