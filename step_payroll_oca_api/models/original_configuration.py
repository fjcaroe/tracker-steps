"""Store the original configuration without pretending unsupported semantics work."""
from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.step_payroll_contracts.history import assert_mutable


RULE_CONFIGURATION_FIELDS = (
    "condition_other_input_id", "amount_other_input_id", "partner_id",
    "not_computed_in_net", "split_move_lines", "condition_select", "amount_select",
)
SUPPORTED_CONDITION_MODES = {"none", "range", "python"}
SUPPORTED_AMOUNT_MODES = {"fix", "percentage", "code"}


class SalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    condition_other_input_id = fields.Many2one(
        "hr.payslip.input.type", string="Condition Other Input", ondelete="set null")
    amount_other_input_id = fields.Many2one(
        "hr.payslip.input.type", string="Amount Other Input", ondelete="set null")
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="set null")
    not_computed_in_net = fields.Boolean(string="Not computed in net accountably")
    split_move_lines = fields.Boolean(string="Split account line based on name")

    def _step_check_original_rule_semantics(self):
        self.check_access("read")
        self.check_field_access_rights("read", list(RULE_CONFIGURATION_FIELDS))
        # These are real references. Inspect them with the caller's access,
        # before reporting unsupported semantics, even with a warm cache.
        (self.condition_other_input_id | self.amount_other_input_id).check_access("read")
        self.partner_id.check_access("read")
        for rule in self:
            if (rule.condition_select not in SUPPORTED_CONDITION_MODES
                    or rule.amount_select not in SUPPORTED_AMOUNT_MODES):
                raise UserError(_("The original payroll rule calculation mode is not supported by Community."))
            if (rule.condition_other_input_id or rule.amount_other_input_id or rule.partner_id
                    or rule.not_computed_in_net or rule.split_move_lines):
                raise UserError(_("Original payroll input, partner or accounting options require a certified Community implementation before processing."))
        return True


class Structure(models.Model):
    _inherit = "hr.payroll.structure"

    active = fields.Boolean(string="Active", default=True)
    hide_basic_on_pdf = fields.Boolean(string="Hide Basic On Pdf")
    payslip_name = fields.Char(string="Payslip Name", translate=True)
    report_id = fields.Many2one("ir.actions.report", string="Template", ondelete="set null")
    # Preserve the complete native JSON property. A global structure has no
    # single company owner; posting must resolve it in the actual slip company.
    journal_id = fields.Many2one(
        "account.journal", string="Salary Journal", company_dependent=True, ondelete="set null")


class Payslip(models.Model):
    _inherit = "hr.payslip"

    def _step_check_original_configuration(self, operation="calculate"):
        """Admission for calculation/posting, never for historical reading.

        The same effective hierarchy and ACL checks used by the actual engine
        remain authoritative. No new parent, owner, rule or journal is chosen.
        The guard is deliberately repeatable without writes or number usage.
        """
        if operation not in {"calculate", "account"}:
            raise UserError(_("Unsupported payroll configuration operation."))
        assert_mutable(self)
        if operation == "account" and any(slip.company_id != self.env.company for slip in self):
            # OCA reads company-dependent rule accounts in env.company. Until
            # orchestration per company is certified, a mixed/wrong context
            # cannot be made safe by merely resolving the journal property.
            raise UserError(_("Select the payslip's original company context before posting payroll."))
        structures = self.env["hr.payroll.structure"]
        rules = self.env["hr.salary.rule"]
        for slip in self:
            for root in slip._step_selected_payroll_structures():
                scope = root._step_effective_rule_scope()
                structures |= scope["structures"]
                rules |= scope["rules"]
        structures.check_access("read")
        structures.check_field_access_rights("read", ["active"])
        if any(not structure.active for structure in structures):
            raise UserError(_("An archived original payroll structure cannot be calculated or posted."))
        rules._step_check_original_rule_semantics()
        if operation == "account":
            for slip in self:
                slip._step_check_original_posting_journal()
        return True

    def _step_check_original_posting_journal(self):
        """Verify compatibility with OCA's actual stored related journal.

        OCA posts through slip.journal_id (contract_id.journal_id). An original
        structure property has not yet acquired precedence over that provider
        policy. Reject a disagreement rather than assign either relationship.
        """
        self.ensure_one()
        self.check_access("read")
        self.check_field_access_rights("read", ["company_id", "contract_id", "journal_id"])
        company = self.company_id
        company.check_access("read")
        if not company or company != self.env.company:
            raise UserError(_("Select the payslip's original company context before posting payroll."))
        if not self.contract_id:
            raise UserError(_("Select the original contract and salary journal before posting payroll."))
        # Reuse the audited actual contract selection and identity checks.
        contract = self._get_employee_contracts()
        contract.check_field_access_rights("read", ["journal_id", "company_id"])
        journal = self.journal_id
        journal.check_access("read")
        journal.check_field_access_rights("read", ["company_id"])
        contract_journal = contract.journal_id
        contract_journal.check_access("read")
        if not journal or journal.company_id != company:
            raise UserError(_("The OCA salary journal must belong to the payslip's original company."))
        if journal != contract_journal:
            raise UserError(_("The original contract salary journal differs from the OCA posting journal."))
        for structure in self._step_selected_payroll_structures():
            original = structure.with_company(company)
            original.check_access("read")
            original.check_field_access_rights("read", ["journal_id"])
            configured_journal = original.journal_id
            configured_journal.check_access("read")
            configured_journal.check_field_access_rights("read", ["company_id"])
            if configured_journal and configured_journal.company_id != company:
                raise UserError(_("The original structure salary journal must belong to the payslip's original company."))
            if configured_journal and configured_journal != journal:
                raise UserError(_("The original structure salary journal differs from the OCA posting journal; adopt its accounting policy before posting."))
        return True

    def compute_sheet(self):
        # OCA deletes old lines and takes a number before asking for rules.
        # Reject unsupported original configuration before either mutation.
        self._step_check_original_configuration(operation="calculate")
        return super().compute_sheet()

    def get_lines_dict(self):
        # This is OCA's real calculation API; its legacy _get_payslip_lines
        # delegates here. Preserve the complete provider chain and ordering.
        self._step_check_original_configuration(operation="calculate")
        return super().get_lines_dict()

    def action_payslip_done(self):
        # payroll_account calls super (changing state) before creating moves.
        # Revalidate changes made after calculation before entering that chain.
        self._step_check_original_configuration(operation="account")
        return super().action_payslip_done()
