# -*- coding: utf-8 -*-
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLegalWorkweekCalendar(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Calendar = cls.env["hr.legal.workweek.calendar"]

    def test_effective_hours_by_date(self):
        """Debe devolver 44h antes de 2026-04-26, 42h entre esa fecha y
        2028-04-26, y 40h desde el 2028-04-26 en adelante — sin importar
        si el módulo se instala antes o después de esas fechas."""
        _rec, hours_2025 = self.Calendar.get_effective_hours(date(2025, 1, 1))
        self.assertEqual(hours_2025, 44)

        _rec, hours_2027 = self.Calendar.get_effective_hours(date(2027, 1, 1))
        self.assertEqual(hours_2027, 42)

        _rec, hours_2028 = self.Calendar.get_effective_hours(date(2028, 4, 26))
        self.assertEqual(hours_2028, 40)

        _rec, hours_2030 = self.Calendar.get_effective_hours(date(2030, 1, 1))
        self.assertEqual(hours_2030, 40)

    def test_official_row_protected(self):
        official = self.Calendar.search([("is_official", "=", True)], limit=1)
        self.assertTrue(official)
        with self.assertRaises(UserError):
            official.write({"max_weekly_hours": 999})

    def test_official_row_unlink_protected(self):
        official = self.Calendar.search([("is_official", "=", True)], limit=1)
        with self.assertRaises(UserError):
            official.unlink()

    def test_custom_row_editable_without_technical_group(self):
        custom = self.Calendar.create(
            {"date_from": date(2029, 1, 1), "max_weekly_hours": 38}
        )
        custom.write({"max_weekly_hours": 37})
        self.assertEqual(custom.max_weekly_hours, 37)

    def test_upcoming_transition(self):
        upcoming = self.Calendar.get_upcoming_transition(date(2025, 1, 1))
        self.assertEqual(upcoming.max_weekly_hours, 42)
        upcoming = self.Calendar.get_upcoming_transition(date(2027, 1, 1))
        self.assertEqual(upcoming.max_weekly_hours, 40)

    def test_cron_idempotent_alert(self):
        """Correr el cron dos veces el mismo día no debe duplicar la
        actividad de alerta."""
        calendar_2028 = self.env.ref(
            "step_hr_contract_lifecycle.legal_workweek_2028"
        )
        # Nos ubicamos artificialmente a 30 días de la transición.
        threshold_date = date(2028, 3, 27)  # 30 días antes del 2028-04-26
        import odoo.fields as odoo_fields

        original = odoo_fields.Date.context_today
        odoo_fields.Date.context_today = staticmethod(lambda *a, **k: threshold_date)
        try:
            self.Calendar._cron_check_legal_calendar_transitions()
            count_after_first = self.env["mail.activity"].search_count(
                [
                    ("res_model", "=", "hr.legal.workweek.calendar"),
                    ("res_id", "=", calendar_2028.id),
                ]
            )
            self.Calendar._cron_check_legal_calendar_transitions()
            count_after_second = self.env["mail.activity"].search_count(
                [
                    ("res_model", "=", "hr.legal.workweek.calendar"),
                    ("res_id", "=", calendar_2028.id),
                ]
            )
        finally:
            odoo_fields.Date.context_today = original
        self.assertEqual(count_after_first, 1)
        self.assertEqual(count_after_second, 1, "El cron no debe duplicar la alerta")


@tagged("post_install", "-at_install")
class TestContractAdequacyBatch(TransactionCase):
    def test_approve_requires_distribution_note(self):
        company = self.env["res.company"].create({"name": "Private adequacy batch fixture"})
        self.env["ir.sequence"].create({"name": "Private adequacy batch numbering",
            "code": "hr.contract.adequacy.batch", "company_id": company.id,
            "prefix": "PRIVATE-ADEQUACY/"})
        Batch = self.env["hr.contract.adequacy.batch"].with_company(company)
        scope = self.env["hr.contract"].with_company(company).env
        journal = scope["account.journal"].create({"name": "Private adequacy journal", "code": "PAD",
            "type": "general", "company_id": company.id})
        kind = scope["hr.payroll.structure.type"].create({"name": "Private adequacy structure type"})
        values = {"name": "Private adequacy structure", "code": "PRIVATE_ADEQUACY", "type_id": kind.id}
        for name, value in (("company_id", company.id), ("parent_id", False),
                            ("use_worked_day_lines", False), ("journal_id", journal.id)):
            if name in scope["hr.payroll.structure"]._fields:
                values[name] = value
        structure = scope["hr.payroll.structure"].create(values)
        work_calendar = scope["resource.calendar"].create({"name": "Private adequacy 45-hour calendar",
            "company_id": company.id, "tz": "UTC", "attendance_ids": [Command.clear()] + [Command.create({
                "name": "Private adequacy shift", "dayofweek": str(day), "hour_from": 8, "hour_to": 17,
                "day_period": "morning"}) for day in range(5)]})
        employee = scope["hr.employee"].create({"name": "Private adequacy employee", "company_id": company.id,
            "resource_calendar_id": work_calendar.id})
        values = {"name": "Private adequacy contract", "employee_id": employee.id, "company_id": company.id,
            "state": "open", "date_start": date(2026, 10, 1), "wage": 800000,
            "structure_type_id": kind.id, "resource_calendar_id": work_calendar.id}
        for name, value in (("struct_id", structure.id), ("journal_id", journal.id)):
            if name in scope["hr.contract"]._fields:
                values[name] = value
        if "contract_type_id" in scope["hr.contract"]._fields:
            model = scope["hr.contract"]._fields["contract_type_id"].comodel_name
            values["contract_type_id"] = scope[model].search([], limit=1).id
        field = scope["hr.contract"]._fields.get("analytic_account_id")
        if field and field.required:
            plan = scope["account.analytic.plan"].create({"name": "Private adequacy analytic plan"})
            values["analytic_account_id"] = scope["account.analytic.account"].create({
                "name": "Private adequacy cost center", "company_id": company.id, "plan_id": plan.id}).id
        contract = scope["hr.contract"].create(values)
        contract.resource_calendar_id = work_calendar
        employee.resource_calendar_id = work_calendar
        employee.resource_id.tz = "UTC"
        approver = scope["res.users"].with_context(no_reset_password=True).create({
            "name": "Private adequacy approver", "login": "private-adequacy-approver",
            "email": "private-adequacy@example.invalid", "company_id": company.id,
            "company_ids": [Command.set(company.ids)], "groups_id": [Command.set([scope.ref(group).id for group in (
                "base.group_user", "hr.group_hr_manager", "hr_contract.group_hr_contract_manager",
                "step_hr_contract_lifecycle.group_contract_adequacy_approve")])]})
        calendar = self.env.ref("step_hr_contract_lifecycle.legal_workweek_2028")
        batch = Batch.create(
            {"calendar_id": calendar.id, "company_id": company.id}
        )
        self.assertTrue(batch.name.startswith("PRIVATE-ADEQUACY/"))
        batch.action_simulate()
        self.assertEqual(batch.line_ids.contract_id, contract)
        self.assertEqual(batch.line_ids.current_weekly_hours, 45)
        self.assertFalse(batch.line_ids.distribution_note)
        target = batch.with_user(approver).with_company(company)
        self.assertTrue(target.env.user.has_group("step_hr_contract_lifecycle.group_contract_adequacy_approve"))
        with self.assertRaises(UserError):
            target.action_approve()
        self.assertEqual(batch.state, "simulated")
