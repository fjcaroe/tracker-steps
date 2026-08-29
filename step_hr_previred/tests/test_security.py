"""Pruebas de permisos y validación en servidor.

Cubre el caso 9 (tres roles y parámetros manipulados) y el caso 12 (ninguna
acción externa).
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged  # noqa: F401
from odoo.tests.common import new_test_user

from .common import PreviredCase, make_row


@tagged("post_install", "-at_install")
class TestSecurity(PreviredCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.viewer = new_test_user(
            cls.env, login="previred_viewer",
            groups="step_hr_previred.group_previred_summary",
            company_id=cls.company.id,
            company_ids=[(6, 0, cls.company.ids)])
        cls.generator = new_test_user(
            cls.env, login="previred_generator",
            groups="step_hr_previred.group_previred_generate",
            company_id=cls.company.id,
            company_ids=[(6, 0, cls.company.ids)])
        cls.outsider = new_test_user(
            cls.env, login="previred_outsider", groups="base.group_user",
            company_id=cls.company.id,
            company_ids=[(6, 0, cls.company.ids)])

    def _wizard(self, user, **values):
        return self.env["step.previred.export.wizard"].with_user(user).create(
            dict({
                "company_id": self.company.id,
                "date_from": self.date_from,
                "date_to": self.date_to,
            }, **values))

    # -- roles ---------------------------------------------------------------

    def test_user_without_any_group_cannot_open_the_wizard(self):
        with self.assertRaises(AccessError):
            self._wizard(self.outsider)

    def test_viewer_can_validate_but_not_generate(self):
        wizard = self._wizard(self.viewer)
        with self.assertRaises(AccessError):
            wizard._ensure_export_permission()

    def test_generator_passes_the_permission_check(self):
        wizard = self._wizard(self.generator)
        wizard._ensure_export_permission()  # no debe lanzar

    def test_only_technical_group_may_edit_profiles(self):
        """El core ya no siembra perfiles: los aporta el bridge del motor."""
        profile = self.env["step.previred.profile"].search([], limit=1)
        if not profile:
            self.skipTest("No hay ningún bridge de motor instalado.")
        with self.assertRaises(AccessError):
            profile.with_user(self.generator).write({"spec_version": "99"})

    def test_audit_log_is_readable_only_with_the_audit_group(self):
        batch = self.env["step.previred.batch"].sudo().create({
            "company_id": self.company.id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "result": "ok",
        })
        with self.assertRaises(AccessError):
            batch.with_user(self.generator).read(["worker_count"])

    # -- parámetros manipulados ---------------------------------------------

    def test_company_outside_allowed_companies_is_rejected(self):
        """No basta con enviar otro `company_id`: se revalida en servidor."""
        wizard = self._wizard(self.generator)
        wizard.sudo().company_id = self.other_company
        with self.assertRaises(AccessError):
            wizard._validate_parameters()

    def test_partial_month_is_rejected(self):
        wizard = self._wizard(self.generator,
                              date_from="2026-08-05", date_to="2026-08-31")
        with self.assertRaises(UserError):
            wizard._validate_parameters()

    def test_period_spanning_two_months_is_rejected(self):
        wizard = self._wizard(self.generator,
                              date_from="2026-08-01", date_to="2026-09-30")
        with self.assertRaises(UserError):
            wizard._validate_parameters()

    def test_department_of_another_company_is_rejected(self):
        wizard = self._wizard(self.generator)
        wizard.sudo().department_ids = self.dep_agri_other
        with self.assertRaises(UserError):
            wizard._validate_parameters()

    def test_full_month_is_accepted(self):
        wizard = self._wizard(self.generator)
        profile = wizard._validate_parameters()
        self.assertTrue(profile)

    # -- auditoría sin datos personales --------------------------------------

    def test_audit_record_carries_no_personal_data(self):
        employee = self.make_employee("Ana Rojas", "11111111-1",
                                      self.dep_agri)
        self.make_payslip(employee, self.dep_agri)
        dataset = self.build([make_row(rut="11111111", dv="1")])
        wizard = self._wizard(self.generator)
        batch = self.env["step.previred.batch"].record(
            wizard, dataset, "consolidated", "txt")
        stored = " ".join(
            str(value) for value in batch.sudo().read()[0].values())
        self.assertNotIn("11111111", stored)
        self.assertNotIn("Ana Rojas", stored)
        self.assertEqual(batch.worker_count, 1)

    # -- caso 12: sin efectos externos ---------------------------------------

    def test_module_declares_no_outbound_calls(self):
        """El módulo no envía a Previred, no escribe liquidaciones y no
        publica asientos: sólo lee y genera archivos."""
        import os
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        forbidden = re.compile(
            r"\b(requests\.|urlopen|smtplib|send_mail|message_post\(|"
            r"action_post\(|_post\(|compute_sheet\(|action_payslip_done)")
        offenders = []
        for folder, _dirs, files in os.walk(root):
            if "tests" in folder or "__pycache__" in folder:
                continue
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as handle:
                    for number, line in enumerate(handle, start=1):
                        if forbidden.search(line):
                            offenders.append("%s:%d" % (name, number))
        self.assertEqual(offenders, [], "Llamadas con efecto externo: %s"
                         % ", ".join(offenders))
