"""Apply accumulated negative-net reporting through the native SyS deduction master."""
from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_amount


class Payslip(models.Model):
    _inherit = "hr.payslip"

    negative_net_to_report_amount = fields.Float(compute="_compute_negative_notice")
    sys_negative_activity_count = fields.Integer(compute="_compute_sys_negative_activity_count")

    def _sys_pending_nets(self):
        self.ensure_one()
        if not self.employee_id or not self.company_id or self.state not in ("draft", "verify"):
            return self.env["hr.payslip"]
        pending = self.search([("employee_id", "=", self.employee_id.id), ("company_id", "=", self.company_id.id),
                               ("has_negative_net_to_report", "=", True), ("id", "!=", self._origin.id or 0)], order="id")
        pending.check_field_access_rights("read", ["net_wage", "has_negative_net_to_report"])
        return pending

    @api.depends("state", "employee_id", "company_id", "employee_id.slip_ids.has_negative_net_to_report",
                 "employee_id.slip_ids.net_wage")
    @api.depends_context("uid", "company")
    def _compute_negative_notice(self):
        for slip in self:
            pending = slip._sys_pending_nets()
            amount = sum(pending.mapped("net_wage"))
            slip.negative_net_to_report_amount = amount
            slip.negative_net_to_report_display = bool(amount)
            slip.negative_net_to_report_message = (_("Neto pendiente de aplicar: %s", format_amount(
                slip.env, amount, slip.company_id.currency_id)) if amount else False)
            if amount and slip.state == "verify" and isinstance(slip.id, int):
                slip._sys_ensure_negative_activity()

    def _sys_ensure_negative_activity(self):
        activities = self.env["mail.activity"]
        domain = self._negative_activity_domain()
        if activities.search_count(domain, limit=1):
            return
        # Two concurrent first reads of the same verification screen must serialize even under repeatable read.
        # An identical tuple gives a competing transaction an Odoo-retryable serialization error without
        # changing the business data or audit metadata of the slip.
        self.env.cr.execute("UPDATE hr_payslip SET id=id WHERE id=%s AND state='verify'", (self.id,))
        if not self.env.cr.rowcount or activities.search_count(domain, limit=1):
            return
        user = self.contract_id.hr_responsible_id or self.env.user
        self.activity_schedule("hr_payroll.mail_activity_data_hr_payslip_negative_net",
                               date_deadline=fields.Date.context_today(self), user_id=user.id,
                               summary=_("Neto pendiente de aplicar"),
                               note=_("Revise el neto pendiente en esta liquidación antes de confirmarla."))

    @api.depends("activity_ids.activity_type_id")
    def _compute_sys_negative_activity_count(self):
        for slip in self:
            slip.sys_negative_activity_count = (
                self.env["mail.activity"].search_count(slip._negative_activity_domain()) if slip._origin.id else 0
            )

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form" and view == self.env.ref("hr_payroll.view_hr_payslip_form", raise_if_not_found=False):
            for box in arch.xpath(".//div[@name='button_box']"):
                button = etree.SubElement(box, "button", type="object", name="action_sys_open_negative_activities",
                                          icon="fa-calendar", invisible="not sys_negative_activity_count")
                button.set("class", "oe_stat_button")
                etree.SubElement(button, "field", name="sys_negative_activity_count", widget="statinfo",
                                 string=_("Actividades de neto negativo"))
        return arch, view

    def action_report_negative_amount(self):
        self.ensure_one()
        self.check_access("write")
        self.check_field_access_rights("write", ["input_line_ids"])
        if not self.id or self.state not in ("draft", "verify") or self.paid:
            raise UserError(_("Aplique el neto pendiente en un borrador de liquidación."))
        if self.company_id != self.env.company or self.employee_id.company_id != self.company_id:
            raise UserError(_("La liquidación debe pertenecer a la empresa seleccionada."))

        with self.env.cr.savepoint():
            self.flush_model(["employee_id", "company_id", "state", "has_negative_net_to_report", "net_wage"])
            # Serialize spending the same pending amount on two drafts. Ordinary Odoo transaction retry handles contention.
            self.env.cr.execute("""SELECT id FROM hr_payslip WHERE id=%s OR
                (employee_id=%s AND company_id=%s AND has_negative_net_to_report) ORDER BY id FOR UPDATE""",
                (self.id, self.employee_id.id, self.company_id.id))
            locked = {i for i, in self.env.cr.fetchall()} - {self.id}
            pending = self._sys_pending_nets()
            if set(pending.ids) != locked:
                raise UserError(_("La operación requiere acceso a todos los recibos pendientes del trabajador."))
            pending.check_access("write")
            pending.check_field_access_rights("write", ["has_negative_net_to_report"])
            amount = abs(sum(pending.mapped("net_wage")))
            if not amount:
                return
            kind = self.env.ref("hr_payroll.input_deduction")
            kind.check_access("read")
            if kind.code != "DEDUCTION":
                raise UserError(_("Revise el tipo de deducción registrado para este neto."))
            entry = self.env["hr.payslip.input"].create({"payslip_id": self.id, "input_type_id": kind.id,
                                                         "name": False, "amount": amount})
            entry.flush_recordset()
            self.env.cr.execute("SELECT set_config('steps.negative_net_input',%s,true), "
                                "set_config('steps.negative_net_sources',%s,true)",
                                (str(entry.id), ",".join(map(str, pending.ids))))
            pending.write({"has_negative_net_to_report": False})
            pending.flush_recordset(["has_negative_net_to_report", "write_uid", "write_date"])
            self.env.cr.execute("SELECT set_config('steps.negative_net_input','',true), "
                                "set_config('steps.negative_net_sources','',true)")
            self.invalidate_recordset(["negative_net_to_report_amount", "negative_net_to_report_display",
                                      "negative_net_to_report_message"])
            # The original settlement recalculates silently. Its optional activity posts its own completion.
            self.with_context(tracking_disable=True).compute_sheet()
            activities = self.env["mail.activity"].search(self._negative_activity_domain())
            if activities:
                activities.action_feedback()
