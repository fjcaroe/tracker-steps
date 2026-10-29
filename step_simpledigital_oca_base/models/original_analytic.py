"""Original per-company rule analytics on the actual LGPL OCA posting chain."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _checked_account(env, ident, company):
    normal = env["account.analytic.account"].sudo(False)
    account = normal.browse(ident)
    account.check_access("read")
    account.check_field_access_rights("read", ["company_id"])
    if not account.exists():
        raise UserError(_("The original payroll analytic account is missing."))
    if account.company_id and account.company_id != company:
        raise UserError(_("The original payroll analytic account must belong to the payslip company or be shared."))
    return account


class SalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    analytic_account_id = fields.Many2one(
        "account.analytic.account", company_dependent=True, copy=False, ondelete="set null")

    def _step_original_analytic_account(self):
        """Resolve the stored company slot, never an unapproved ir.default."""
        self.ensure_one()
        if self._name != "hr.salary.rule":
            raise ValueError("Expected an original salary rule, not an inherited line snapshot")
        normal = self.sudo(False)
        normal.check_access("read")
        normal.check_field_access_rights("read", ["analytic_account_id", "company_id"])
        company = normal.env.company
        if normal.company_id and normal.company_id != company:
            raise UserError(_("Select the original payroll rule company before resolving its analytic property."))
        normal.flush_recordset(["analytic_account_id"])
        normal.env.cr.execute("SELECT analytic_account_id,analytic_account_id IS NULL FROM hr_salary_rule WHERE id=%s", (normal.id,))
        row = normal.env.cr.fetchone()
        if row is None:
            raise UserError(_("The original payroll analytic property is unavailable."))
        stored = row[0]
        if row[1]:
            if normal.analytic_account_id:
                raise UserError(_("An implicit payroll analytic default is not an adopted original company property."))
            return normal.env["account.analytic.account"]
        key = str(company.id)
        if not isinstance(stored, dict) or key not in stored:
            raise UserError(_("The original payroll analytic property is incomplete for the payslip company."))
        ident = stored[key]
        if ident is None or ident is False:
            if normal.analytic_account_id:
                raise UserError(_("The original payroll analytic property does not resolve its exact company value."))
            return normal.env["account.analytic.account"]
        if not isinstance(ident, int) or isinstance(ident, bool) or not 0 < ident < 2**31:
            raise UserError(_("The original payroll analytic property has an invalid account reference."))
        account = _checked_account(normal.env, ident, company)
        if normal.analytic_account_id != account:
            raise UserError(_("The original payroll analytic property does not resolve its exact company value."))
        return account

    @api.model_create_multi
    def create(self, vals_list):
        if self._name != "hr.salary.rule":
            return super().create(vals_list)
        self.sudo(False).check_access("create")
        # Defaults can be applied inside super.create.  Validate its real
        # stored result within a savepoint too, so caught errors are atomic.
        with self.env.cr.savepoint():
            records = super().create(vals_list)
            for record in records:
                record._step_original_analytic_account()
            return records

    def write(self, vals):
        if self._name != "hr.salary.rule" or "analytic_account_id" not in vals:
            return super().write(vals)
        normal = self.sudo(False)
        normal.check_access("write")
        normal.check_field_access_rights("write", ["analytic_account_id"])
        with self.env.cr.savepoint():
            result = super().write(vals)
            for record in normal:
                record._step_original_analytic_account()
            return result


class PayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    # OCA uses classical inheritance from hr.salary.rule.  Its line field is
    # an independent scalar extension, absent from the native line contract;
    # do not turn paid historical rows into company-dependent properties.
    analytic_account_id = fields.Many2one(
        "account.analytic.account", company_dependent=False, copy=True, ondelete="set null")


class Payslip(models.Model):
    _inherit = "hr.payslip"

    def _step_original_analytic_distribution(self, rule):
        self.ensure_one()
        normal = self.sudo(False)
        normal.check_access("read")
        normal.check_field_access_rights("read", ["company_id", "contract_id"])
        company = normal.company_id
        if not company or company != normal.env.company:
            raise UserError(_("Select the payslip's original company context before posting payroll analytics."))
        contract = normal.contract_id
        contract.check_access("read")
        contract.check_field_access_rights("read", ["company_id", "analytic_account_id"])
        if not contract or contract.company_id != company:
            raise UserError(_("Payroll analytics require the original contract in the payslip company."))
        # This is OCA's actual priority, not a claim about the native engine.
        if contract.analytic_account_id:
            account = _checked_account(normal.env, contract.analytic_account_id.id, company)
        else:
            account = rule.with_env(normal.env)._step_original_analytic_account()
        return {account.id: 100} if account else {}

    def _step_check_original_configuration(self, operation="calculate"):
        normal = self.sudo(False)
        result = super(Payslip, normal)._step_check_original_configuration(operation=operation)
        if operation == "account":
            for slip in normal:
                rules = normal.env["hr.salary.rule"]
                for structure in slip._step_selected_payroll_structures():
                    rules |= structure._step_effective_rule_scope()["rules"]
                # without_compute_sheet posts existing real lines.  Check the
                # complete membership before OCA can filter hidden children.
                lines = normal.env["hr.payslip.line"]
                lines.check_access("read")
                lines.check_field_access_rights("read", ["slip_id", "salary_rule_id"])
                lines.flush_model(["slip_id", "salary_rule_id"])
                normal.env.cr.execute("SELECT id,salary_rule_id FROM hr_payslip_line WHERE slip_id=%s", (slip.id,))
                rows = normal.env.cr.fetchall()
                members = lines.with_context(active_test=False).browse([row[0] for row in rows])
                members.check_access("read")
                if any(not row[1] for row in rows):
                    raise UserError(_("The original payroll line salary rule identity is missing."))
                rules |= normal.env["hr.salary.rule"].browse([row[1] for row in rows if row[1]])
                rules.check_access("read")
                for rule in rules:
                    slip._step_original_analytic_distribution(rule)
        return result

    def _step_check_prepared_analytic(self, line, provided):
        normal_line = line.sudo(False)
        normal_line.check_access("read")
        normal_line.check_field_access_rights("read", ["slip_id", "salary_rule_id"])
        expected = normal_line.slip_id._step_original_analytic_distribution(normal_line.salary_rule_id)
        if provided != expected:
            raise UserError(_("The OCA payroll analytic distribution differs from the original company property."))
        return expected

    def _prepare_debit_line(self, line, amount, date, debit_account_id, move_line_analytic_ids):
        expected = self._step_check_prepared_analytic(line, move_line_analytic_ids)
        result = super()._prepare_debit_line(line, amount, date, debit_account_id, move_line_analytic_ids)
        if result.get("analytic_distribution") != expected:
            raise UserError(_("The OCA payroll analytic distribution changed during debit preparation."))
        return result

    def _prepare_credit_line(self, line, amount, date, credit_account_id, move_line_analytic_ids):
        expected = self._step_check_prepared_analytic(line, move_line_analytic_ids)
        result = super()._prepare_credit_line(line, amount, date, credit_account_id, move_line_analytic_ids)
        if result.get("analytic_distribution") != expected:
            raise UserError(_("The OCA payroll analytic distribution changed during credit preparation."))
        return result
