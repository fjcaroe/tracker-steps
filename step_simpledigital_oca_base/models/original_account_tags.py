"""Original tax-grid relations with ordinary-actor admission for OCA posting."""
from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError


TAG_RELATIONS = {
    'debit_tag_ids': 'hr_salary_rule_debit_tag_rel',
    'credit_tag_ids': 'hr_salary_rule_credit_tag_rel',
}


class SalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    debit_tag_ids = fields.Many2many(
        'account.account.tag', 'hr_salary_rule_debit_tag_rel', 'hr_salary_rule_id', 'account_account_tag_id',
        string='Debit Tax Grids', domain=[('applicability', '=', 'taxes')], ondelete='cascade')
    credit_tag_ids = fields.Many2many(
        'account.account.tag', 'hr_salary_rule_credit_tag_rel', 'hr_salary_rule_id', 'account_account_tag_id',
        string='Credit Tax Grids', domain=[('applicability', '=', 'taxes')], ondelete='cascade')

    def _step_original_account_tag_members(self, field_name):
        """Read complete actual pairs only after authorizing the rule and field.

        An ORM-filtered M2M must not turn a hidden tax-grid contribution into an
        incomplete accounting entry. This reader never evaluates salary rules.
        """
        self.ensure_one()
        if self._name != 'hr.salary.rule' or field_name not in TAG_RELATIONS:
            raise ValueError('Expected an original salary-rule tax-grid relation')
        normal = self.sudo(False)
        normal.check_access('read')
        normal.check_field_access_rights('read', [field_name])
        normal.flush_recordset([field_name])
        normal.env.cr.execute('SELECT account_account_tag_id FROM ' + TAG_RELATIONS[field_name]
            + ' WHERE hr_salary_rule_id=%s ORDER BY account_account_tag_id', (normal.id,))
        ids = [row[0] for row in normal.env.cr.fetchall()]
        tags = normal.env['account.account.tag'].with_context(active_test=False).browse(ids)
        if not ids:
            return tags
        tags.check_access('read')
        if set(tags.exists().ids) != set(ids):
            raise UserError(_('An original payroll tax grid is missing.'))
        return tags

    def _step_original_account_tags(self, field_name, company):
        self.ensure_one()
        normal = self.sudo(False)
        normal.check_access('read')
        normal.check_field_access_rights('read', ['company_id', field_name])
        if company._name != 'res.company' or company != normal.env.company:
            raise UserError(_("Select the payslip's original company before posting payroll tax grids."))
        company = company.with_env(normal.env)
        if normal.company_id and normal.company_id != company:
            raise UserError(_('The original payroll tax-grid rule is outside the payslip company.'))
        tags = normal._step_original_account_tag_members(field_name)
        if not tags:
            return tags
        company.check_access('read')
        company.check_field_access_rights('read', ['account_fiscal_country_id'])
        tags.check_field_access_rights('read', ['active', 'applicability', 'country_id'])
        if any(not tag.active or tag.applicability != 'taxes' for tag in tags):
            raise UserError(_('Payroll posting requires active tax grids, not account or product tags.'))
        if any(tag.country_id and tag.country_id != company.account_fiscal_country_id for tag in tags):
            raise UserError(_('The original payroll tax grid must match the payslip fiscal country or be shared.'))
        return tags

    def _step_original_account_tag_copy_plan(self, default=None):
        """Authorize every source pair before considering any replacement.

        Read domains are selection aids, not authority to silently discard a
        visible incompatible original value while duplicating a real rule.
        """
        normal = self.sudo(False)
        plan = {record.id: {name: set(record._step_original_account_tag_members(name).ids)
                           for name in TAG_RELATIONS} for record in normal}
        for name in TAG_RELATIONS.keys() & (default or {}).keys():
            value = default[name]
            ids, references = set(), set()
            if value is None or value is False:
                commands = []
            elif getattr(value, '_name', None) == 'account.account.tag':
                commands = [Command.set(value.ids)]
            elif isinstance(value, (tuple, list)):
                commands = value
            else:
                raise UserError(_('Unsupported original tax-grid copy default.'))
            for command in commands:
                if not isinstance(command, (tuple, list)) or len(command) != 3:
                    raise UserError(_('Unsupported original tax-grid copy default.'))
                operation, ident, values = command
                if operation == Command.SET and ident == 0 and isinstance(values, (tuple, list)):
                    if any(type(item) is not int or not 0 < item < 2**31 for item in values):
                        raise UserError(_('Invalid original tax-grid copy reference.'))
                    ids = set(values)
                    references.update(ids)
                elif operation in (Command.LINK, Command.UNLINK) and values == 0 and type(ident) is int and 0 < ident < 2**31:
                    references.add(ident)
                    if operation == Command.LINK:
                        ids.add(ident)
                    else:
                        ids.discard(ident)
                elif operation == Command.CLEAR and ident == 0 and values == 0:
                    ids.clear()
                else:
                    raise UserError(_('Copying payroll tax grids cannot change tag masters.'))
            targets = normal.env['account.account.tag'].with_context(active_test=False).browse(sorted(references))
            if references:
                targets.check_access('read')
                if set(targets.exists().ids) != references:
                    raise UserError(_('An original tax-grid copy reference is missing.'))
            for record in normal:
                plan[record.id][name] = set(ids)
        return plan

    def copy_data(self, default=None):
        if self._name != 'hr.salary.rule':
            return super().copy_data(default=default)
        normal = self.sudo(False)
        plan = normal._step_original_account_tag_copy_plan(default)
        # Do not pass master-changing commands to any provider copy hook.
        safe_default = dict(default or {})
        for name in TAG_RELATIONS.keys() & safe_default.keys():
            if normal:
                safe_default[name] = [Command.set(sorted(plan[normal[0].id][name]))]
        result = super(SalaryRule, normal).copy_data(default=safe_default)
        for record, values in zip(normal, result):
            if values is not None:
                for name in TAG_RELATIONS:
                    values[name] = [Command.set(sorted(plan[record.id][name]))]
        return result

    def copy(self, default=None):
        if self._name != 'hr.salary.rule':
            return super().copy(default=default)
        normal = self.sudo(False)
        plan = normal._step_original_account_tag_copy_plan(default)
        normal.check_access('create')
        with self.env.cr.savepoint():
            result = super(SalaryRule, normal).copy(default=default)
            if len(result) != len(normal):
                raise UserError(_('The original payroll tax-grid copy is incomplete.'))
            for source, copied in zip(normal, result):
                for name in TAG_RELATIONS:
                    if set(copied._step_original_account_tag_members(name).ids) != plan[source.id][name]:
                        raise UserError(_('The original payroll tax-grid pairs changed during copy.'))
            return result


class PayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    # OCA's classical rule inheritance must not reuse the master M2M table for
    # salary-line IDs or invent a new historical relation. Native line fields
    # are nonstored and read-only; these are current configuration projections,
    # never authoritative tax-grid snapshots for an already posted move.
    debit_tag_ids = fields.Many2many(
        'account.account.tag', compute='_compute_original_account_tags', compute_sudo=False,
        readonly=True, store=False, copy=False, domain=[])
    credit_tag_ids = fields.Many2many(
        'account.account.tag', compute='_compute_original_account_tags', compute_sudo=False,
        readonly=True, store=False, copy=False, domain=[])

    @api.depends('salary_rule_id', 'salary_rule_id.debit_tag_ids', 'salary_rule_id.credit_tag_ids')
    @api.depends_context('uid')
    def _compute_original_account_tags(self):
        for line in self:
            normal = line.sudo(False)
            normal.check_access('read')
            normal.check_field_access_rights('read', ['salary_rule_id', 'debit_tag_ids', 'credit_tag_ids'])
            for field_name in TAG_RELATIONS:
                line[field_name] = normal.salary_rule_id._step_original_account_tag_members(field_name) if normal.salary_rule_id else normal.env['account.account.tag']


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def _step_check_original_configuration(self, operation='calculate'):
        normal = self.sudo(False)
        result = super(Payslip, normal)._step_check_original_configuration(operation=operation)
        if operation == 'account':
            for slip in normal:
                rules = slip._get_salary_rules()
                lines = normal.env['hr.payslip.line']
                lines.check_access('read')
                lines.check_field_access_rights('read', ['slip_id', 'salary_rule_id'])
                lines.flush_model(['slip_id', 'salary_rule_id'])
                normal.env.cr.execute('SELECT id,salary_rule_id FROM hr_payslip_line WHERE slip_id=%s', (slip.id,))
                rows = normal.env.cr.fetchall()
                lines.browse([row[0] for row in rows]).check_access('read')
                if any(not row[1] for row in rows):
                    raise UserError(_('The original payroll line salary rule identity is missing.'))
                rules |= normal.env['hr.salary.rule'].browse([row[1] for row in rows])
                for rule in rules:
                    for field_name in TAG_RELATIONS:
                        rule._step_original_account_tags(field_name, slip.company_id)
        return result

    def _step_prepare_original_account_tags(self, line, field_name):
        normal_line = line.sudo(False)
        normal_line.check_access('read')
        normal_line.check_field_access_rights('read', ['slip_id', 'salary_rule_id'])
        slip = normal_line.slip_id
        slip.check_access('read')
        slip.check_field_access_rights('read', ['company_id'])
        return normal_line.salary_rule_id._step_original_account_tags(field_name, slip.company_id)

    def _step_merge_original_account_tags(self, result, tags):
        if not tags:
            return result  # Preserve an existing untagged OCA route exactly.
        normal = self.sudo(False)
        target = normal.env['account.move.line']
        target.check_access('create')
        target.check_field_access_rights('write', ['tax_tag_ids'])
        existing = result.get('tax_tag_ids')
        if existing is None or existing is False:
            ids = set()
        elif getattr(existing, '_name', None) == 'account.account.tag':
            ids = set(existing.ids)
        elif isinstance(existing, (tuple, list)):
            ids = set()
            # Standard relation-only ORM commands are safe to combine on the
            # new move line. Never execute a provider command on tag masters.
            for command in existing:
                if getattr(command, '_name', None) == 'account.account.tag':
                    # Pinned OCA's account_tax_id-only branch starts with []
                    # and extends it with a real tag recordset. Preserve that
                    # list-of-records provider contract as well.
                    ids.update(command.ids)
                    continue
                if not isinstance(command, (tuple, list)) or len(command) != 3:
                    raise UserError(_('Unsupported OCA payroll tax-grid payload.'))
                operation, ident, values = command
                if operation == Command.SET and ident == 0 and isinstance(values, (list, tuple)):
                    if any(type(value) is not int or not 0 < value < 2**31 for value in values):
                        raise UserError(_('Invalid OCA payroll tax-grid reference.'))
                    ids = set(values)
                elif operation == Command.LINK and values == 0:
                    ids.add(ident)
                elif operation == Command.CLEAR and ident == 0 and values == 0:
                    ids.clear()
                elif operation == Command.UNLINK and values == 0:
                    ids.discard(ident)
                else:
                    raise UserError(_('Payroll tax-grid preparation cannot change tag masters.'))
        else:
            raise UserError(_('Unsupported OCA payroll tax-grid payload.'))
        if any(type(ident) is not int or not 0 < ident < 2**31 for ident in ids):
            raise UserError(_('Invalid OCA payroll tax-grid reference.'))
        provider_tags = normal.env['account.account.tag'].with_context(active_test=False).browse(sorted(ids))
        provider_tags.check_access('read')
        if set(provider_tags.exists().ids) != ids:
            raise UserError(_('An OCA payroll tax grid is missing.'))
        # The authoritative OCA payload remains intact apart from this union.
        # Amounts, accounts, tax/tax-repartition references and fiscal inversion
        # are still produced by the actual provider and account engine.
        result['tax_tag_ids'] = [Command.set(sorted(ids | set(tags.ids)))]
        return result

    def _prepare_debit_line(self, line, amount, date, debit_account_id, move_line_analytic_ids):
        tags = self._step_prepare_original_account_tags(line, 'debit_tag_ids')
        result = super()._prepare_debit_line(line, amount, date, debit_account_id, move_line_analytic_ids)
        return self._step_merge_original_account_tags(result, tags)

    def _prepare_credit_line(self, line, amount, date, credit_account_id, move_line_analytic_ids):
        tags = self._step_prepare_original_account_tags(line, 'credit_tag_ids')
        result = super()._prepare_credit_line(line, amount, date, credit_account_id, move_line_analytic_ids)
        return self._step_merge_original_account_tags(result, tags)
