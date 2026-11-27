"""Operator workflow on the original SyS payslip, contract, input and work-entry identities."""
from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class Company(models.Model):
    _inherit = "res.company"

    batch_payroll_move_lines = fields.Boolean()


class ExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    payslip_id = fields.Many2one("hr.payslip", readonly=True)


class WorkedDay(models.Model):
    _inherit = "hr.payslip.worked_days"

    ytd = fields.Monetary(string="YTD")


class PayslipInput(models.Model):
    _inherit = "hr.payslip.input"

    _allowed_input_type_ids = fields.Many2many(related="payslip_id.struct_id.input_line_type_ids", string="Other Input Line")


class Payslip(models.Model):
    _inherit = "hr.payslip"

    country_id = fields.Many2one(related="company_id.country_id")
    country_code = fields.Char(related="country_id.code")
    image_1920 = fields.Image(related="employee_id.image_1920")
    wage_type = fields.Selection(related="contract_id.wage_type")
    step_employee_rut = fields.Char(related="employee_id.identification_id", string="RUT")
    batch_payroll_move_lines = fields.Boolean(related="company_id.batch_payroll_move_lines")
    paid_date = fields.Date(string="Close Date", help="The date on which the payment is made to the employee.")
    warning_message = fields.Char(readonly=True, copy=False)
    sum_worked_hours = fields.Float(readonly=True, copy=False, help="Total hours of attendance and time off (paid or not)")
    has_negative_net_to_report = fields.Boolean()
    has_refund_slip = fields.Boolean(compute="_compute_has_refund_slip")
    contract_domain_ids = fields.Many2many("hr.contract", compute="_compute_contract_domain")
    expense_sheet_ids = fields.One2many("hr.expense.sheet", "payslip_id", string="Expenses", copy=False,
                                        help="Expenses to reimburse to employee.")
    expenses_count = fields.Integer(compute="_compute_expenses_count")
    attendance_count = fields.Integer(compute="_compute_attendance_count")
    negative_net_to_report_display = fields.Boolean(compute="_compute_negative_notice")
    negative_net_to_report_message = fields.Char(compute="_compute_negative_notice")

    @api.depends("refunded_id.state")
    def _compute_has_refund_slip(self):
        for slip in self:
            slip.has_refund_slip = bool(slip.refunded_id and slip.refunded_id.state != "cancel")

    @api.depends("employee_id", "company_id", "date_from", "date_to")
    def _compute_contract_domain(self):
        for slip in self:
            contracts = self.env["hr.contract"]
            if slip.employee_id and slip.date_from and slip.date_to:
                contracts = slip.employee_id._get_contracts(slip.date_from, slip.date_to)
            slip.contract_domain_ids = contracts.filtered(lambda c: c.company_id == slip.company_id)

    @api.depends("expense_sheet_ids")
    def _compute_expenses_count(self):
        for slip in self:
            slip.expenses_count = len(slip.expense_sheet_ids)

    def _period_domain(self, model):
        self.ensure_one()
        if not (self.employee_id and self.contract_id and self.date_from and self.date_to):
            return [("id", "=", False)]
        start, stop = self.contract_id._payroll_period_bounds(self.date_from, self.date_to)
        employee = [("employee_id", "=", self.employee_id.id)]
        if model == "hr.work.entry":
            return employee + [("company_id", "=", self.company_id.id), ("contract_id", "=", self.contract_id.id),
                               ("date_start", "<=", stop), ("date_stop", ">", start)]
        return employee + [("check_in", "<=", stop), "|", ("check_out", "=", False), ("check_out", ">", start)]

    @api.depends("employee_id", "contract_id", "date_from", "date_to")
    def _compute_attendance_count(self):
        for slip in self:
            slip.attendance_count = self.env["hr.attendance"].search_count(slip._period_domain("hr.attendance"))

    def _negative_activity_domain(self):
        self.ensure_one()
        kind = self.env.ref("hr_payroll.mail_activity_data_hr_payslip_negative_net")
        return [("res_model", "=", self._name), ("res_id", "=", self._origin.id or False),
                ("activity_type_id", "=", kind.id)]

    @api.depends("has_negative_net_to_report", "activity_ids.activity_type_id")
    def _compute_negative_notice(self):
        for slip in self:
            pending = slip._origin and self.env["mail.activity"].search_count(slip._negative_activity_domain(), limit=1)
            slip.negative_net_to_report_display = bool(slip.has_negative_net_to_report or pending)
            slip.negative_net_to_report_message = (
                _("Revise el neto negativo registrado en esta liquidación.") if slip.negative_net_to_report_display else False
            )

    @api.onchange("worked_days_line_ids")
    def _onchange_sum_worked_hours(self):
        for slip in self:
            if slip.state in ("draft", "verify") and slip._sys_cl_structure():
                hours = sum(slip.worked_days_line_ids.mapped("number_of_hours"))
                if slip.sum_worked_hours != hours:
                    slip.sum_worked_hours = hours

    @api.model_create_multi
    def create(self, values_list):
        slips = super().create(values_list)
        slips.filtered(lambda slip: slip.state in ("draft", "verify"))._onchange_sum_worked_hours()
        return slips

    def write(self, values):
        result = super().write(values)
        if "worked_days_line_ids" in values:
            self._onchange_sum_worked_hours()
        return result

    def _sys_open_list(self, model, title, domain):
        self.ensure_one()
        self.check_access("read")
        self.env[model].check_access("read")
        return {"type": "ir.actions.act_window", "name": title, "res_model": model,
                "view_mode": "list,form", "views": [(False, "list"), (False, "form")], "domain": domain}

    def action_open_work_entries(self):
        return self._sys_open_list("hr.work.entry", _("Entradas de trabajo"), self._period_domain("hr.work.entry"))

    def action_open_attendances(self):
        return self._sys_open_list("hr.attendance", _("Asistencias"), self._period_domain("hr.attendance"))

    def action_open_expenses(self):
        return self._sys_open_list("hr.expense.sheet", _("Gastos"), [("payslip_id", "=", self.id)])

    def action_sys_open_negative_activities(self):
        return self._sys_open_list("mail.activity", _("Actividades de neto negativo"), self._negative_activity_domain())

    def action_open_move(self):
        self.ensure_one()
        self.check_access("read")
        if not self.move_id:
            raise UserError(_("La liquidación aún no tiene asiento contable."))
        self.move_id.check_access("read")
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": self.move_id.id,
                "views": [(False, "form")], "view_mode": "form"}

    def action_print_payslip(self):
        self.check_access("read")
        return self.env.ref("hr_payroll.action_report_payslip").report_action(self, config=False)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form" and view == self.env.ref("hr_payroll.view_hr_payslip_form", raise_if_not_found=False):
            # Keep the original persisted view and every payroll operation with an active provider.
            unavailable = [] if hasattr(self, "action_export_payslip") else ["action_export_payslip", "is_superuser"]
            if "hr.salary.attachment" not in self.env:
                unavailable += ["action_open_salary_attachments", "salary_attachment_ids"]
            if "planning.slot" not in self.env:
                unavailable.append("action_open_planning_slots")
            for name in unavailable:
                for node in arch.xpath(".//*[@name=$name]", name=name):
                    node.getparent().remove(node)
            if not hasattr(self, "action_report_negative_amount"):
                for button in arch.xpath(".//button[@name='action_report_negative_amount']"):
                    button.set("name", "action_sys_open_negative_activities")
                    button.set("string", _("Ver actividades de neto negativo"))
            for sheets in arch.xpath(".//field[@name='expense_sheet_ids']"):
                # This invisible relation needs its identities, not the finance module's full expense editor.
                for tag in ("list", "form"):
                    if sheets.find(tag) is None:
                        etree.SubElement(etree.SubElement(sheets, tag), "field", name="name")
        return arch, view

    def _sys_cl_structure(self):
        self.ensure_one()
        original = self.env.ref("l10n_cl_simpledigital_payroll.structure_chile", raise_if_not_found=False)
        return bool(original and self.struct_id == original)

    def get_worked_day_lines(self, contracts, date_from, date_to):
        if not self or not self._sys_cl_structure():
            return super().get_worked_day_lines(contracts, date_from, date_to)
        if not self.contract_id or not date_from or not date_to or date_from > date_to:
            return []
        if contracts != self.contract_id or date_from != self.date_from or date_to != self.date_to:
            raise UserError(_("Las entradas de trabajo deben corresponder al contrato y período de la liquidación."))
        return self._get_worked_day_lines()

    @api.onchange("employee_id", "date_from", "date_to")
    def onchange_employee(self):
        for slip in self:
            if slip.contract_id and slip.contract_id.employee_id != slip.employee_id:
                slip.contract_id = False
            if slip.employee_id and slip.date_from and slip.date_to and slip.date_from <= slip.date_to:
                slip.company_id = slip.employee_id.company_id
                if not slip.contract_id:
                    slips_contracts = slip._get_employee_contracts()
                    if len(slips_contracts) == 1:
                        slip.contract_id = slips_contracts
                if slip.contract_id and not slip.struct_id:
                    slip.struct_id = slip.contract_id.struct_id or slip.contract_id.structure_type_id.default_struct_id
        return super().onchange_employee()

    @api.onchange("date_from", "date_to")
    def onchange_dates(self):
        ready = self.filtered(lambda slip: slip.employee_id and slip.date_from and slip.date_to
                              and slip.date_from <= slip.date_to)
        if ready:
            super(Payslip, ready).onchange_dates()

    @api.onchange("struct_id")
    def onchange_struct_id(self):
        # SyS uses the manually selected input types. Keep the operator's typed rows on repeated onchanges.
        for slip in self:
            if not (slip.struct_id and slip.employee_id and slip.contract_id and slip.date_from and slip.date_to):
                continue
            if slip._sys_cl_structure():
                slip._compute_name()
                slip.onchange_dates()
            else:
                super(Payslip, slip).onchange_struct_id()
