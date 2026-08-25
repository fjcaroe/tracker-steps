# -*- coding: utf-8 -*-
from datetime import date

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
        Batch = self.env["hr.contract.adequacy.batch"]
        calendar = self.env.ref("step_hr_contract_lifecycle.legal_workweek_2028")
        batch = Batch.create(
            {"calendar_id": calendar.id, "company_id": self.env.company.id}
        )
        batch.action_simulate()
        if not batch.line_ids:
            self.skipTest("No hay contratos con jornada > 40h en datos de prueba")
        with self.assertRaises(UserError):
            batch.action_approve()
