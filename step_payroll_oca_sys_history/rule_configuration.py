from markupsafe import Markup

from odoo import _, models
from odoo.addons.step_payroll_oca_api.models.payroll import CategoryMapping
from odoo.exceptions import UserError
from odoo.tools import format_date


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

    def action_payslip_done(self):
        structure = self.env.ref('l10n_cl_simpledigital_payroll.structure_chile', raise_if_not_found=False)
        with self.env.cr.savepoint():
            result = super().action_payslip_done()
            for slip in self.filtered(lambda record: record.state == 'done' and not record.move_id):
                if slip.company_id.id != 37 or slip.struct_id != structure:
                    continue
                # SyS retains a draft accounting header even without any rule
                # accounts. The regular payroll provider handles mapped lines.
                if slip.payslip_run_id or slip.credit_note:
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
        if (self.env.company.id != 37 or self.id != 4 or len(rules) != 67
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
