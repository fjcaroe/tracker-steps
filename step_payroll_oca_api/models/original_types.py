"""Original structure-type storage backed by actual OCA and Community APIs."""
from odoo import _, fields, models
from odoo.exceptions import UserError


SCHEDULE_PAY = [
    ("annually", "Annually"), ("semi-annually", "Semi-annually"),
    ("quarterly", "Quarterly"), ("bi-monthly", "Bi-monthly"),
    ("monthly", "Monthly"), ("semi-monthly", "Semi-monthly"),
    ("bi-weekly", "Bi-weekly"), ("weekly", "Weekly"), ("daily", "Daily"),
]


class StructureType(models.Model):
    _inherit = "hr.payroll.structure.type"

    default_schedule_pay = fields.Selection(SCHEDULE_PAY, string="Default Scheduled Pay")
    default_work_entry_type_id = fields.Many2one(
        "hr.work.entry.type", string="Default Work Entry Type", required=True, ondelete="restrict",
        default=lambda self: self._step_default_attendance_type())
    sequence = fields.Integer(string="Sequence")
    # Monthly is already the default of the real StepBase contract bridge and
    # all five original types; an hourly policy remains stored but uncertified.
    wage_type = fields.Selection(
        [("monthly", "Monthly"), ("hourly", "Hourly")], string="Default Wage Type", required=True, default="monthly")

    def _step_default_attendance_type(self):
        # This is the same existing public master selected by official
        # hr_work_entry_contract, never a newly manufactured attendance type.
        attendance = self.env.ref("hr_work_entry.work_entry_type_attendance", raise_if_not_found=False)
        if attendance:
            attendance.check_access("read")
        return attendance.id if attendance else False

    def _step_check_original_type_policy(self):
        self.check_access("read")
        self.check_field_access_rights("read", ["default_schedule_pay", "default_work_entry_type_id", "wage_type"])
        allowed = {key for key, label in self.env["hr.contract"]._fields["schedule_pay"]._description_selection(self.env)}
        for kind in self:
            if kind.wage_type != "monthly":
                raise UserError(_("The original hourly payroll type policy is not certified for Community processing."))
            if kind.default_schedule_pay and kind.default_schedule_pay not in allowed:
                raise UserError(_("The original payroll schedule policy is not supported by the actual OCA contract."))
            kind.default_work_entry_type_id.check_access("read")
            if not kind.default_work_entry_type_id.exists():
                raise UserError(_("Select the original default work entry type before processing payroll."))
        return True


class Contract(models.Model):
    _inherit = "hr.contract"

    def _get_default_work_entry_type_id(self):
        self.ensure_one()
        self.check_field_access_rights("read", ["structure_type_id"])
        kind = self.structure_type_id
        if not kind:
            return super()._get_default_work_entry_type_id()
        kind.check_access("read")
        kind.check_field_access_rights("read", ["default_work_entry_type_id"])
        entry_type = kind.default_work_entry_type_id
        entry_type.check_access("read")
        if not entry_type.exists():
            raise UserError(_("Select the original default work entry type before generating work entries."))
        # No cache keyed solely on the structure type: its explicit default may
        # change for future generation while existing work entries stay intact.
        return entry_type.id


class Payslip(models.Model):
    _inherit = "hr.payslip"

    def _step_check_original_configuration(self, operation="calculate"):
        result = super()._step_check_original_configuration(operation=operation)
        self._get_employee_contracts().structure_type_id._step_check_original_type_policy()
        return result
