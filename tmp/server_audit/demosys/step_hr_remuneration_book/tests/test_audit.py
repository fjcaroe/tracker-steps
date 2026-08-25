"""10. Un solo dataset y un solo registro de auditoría por acción."""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import RemunerationBookCommon

WIZARD = "odoo.addons.step_hr_remuneration_book.models." \
         "hr_libro_remuneraciones_wizard.HrLibroRemuneracionesWizard"


@tagged("post_install", "-at_install")
class TestSingleDatasetAndLog(RemunerationBookCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        employee = cls._create_employee("Auditoría Sintética", "12.345.678-5")
        cls._create_payslip(
            employee, cls._create_contract(employee, cls.department_admin),
            cls._coherent_values(wage=500000))

    def _logs(self, output=None):
        domain = [("company_id", "=", self.company.id)]
        if output:
            domain.append(("output", "=", output))
        return self.env["step.remuneration.book.log"].search(domain)

    def _count_builds(self, callback):
        """Cuenta cuántas veces se construye el dataset en una acción."""
        original = self.env[
            "step.hr.remuneration.book.wizard"
        ].__class__.build_dataset
        calls = []

        def counted(wizard_self, *args, **kwargs):
            calls.append(wizard_self.id)
            return original(wizard_self, *args, **kwargs)

        with patch("%s.build_dataset" % WIZARD, counted):
            callback()
        return len(calls)

    def test_the_button_does_not_build_the_dataset(self):
        wizard = self._wizard()
        builds = self._count_builds(wizard.action_download_xlsx)
        self.assertEqual(builds, 0)
        self.assertFalse(self._logs("xlsx"))

    def test_one_dataset_and_one_log_per_generated_file(self):
        wizard = self._wizard()
        builds = self._count_builds(lambda: wizard.generate("xlsx"))
        self.assertEqual(builds, 1)
        self.assertEqual(len(self._logs("xlsx")), 1)

    def test_pdf_report_builds_once_and_logs_once(self):
        wizard = self._wizard()
        report = self.env["report.step_hr_remuneration_book.consolidated_book"]
        builds = self._count_builds(
            lambda: report._get_report_values(wizard.ids))
        self.assertEqual(builds, 1)
        self.assertEqual(len(self._logs("pdf")), 1)

    def test_employee_sheets_log_their_own_output(self):
        wizard = self._wizard()
        report = self.env["report.step_hr_remuneration_book.employee_sheets"]
        report._get_report_values(wizard.ids)
        self.assertEqual(len(self._logs("sheets")), 1)
        self.assertFalse(self._logs("pdf"))

    def test_preview_logs_exactly_once(self):
        wizard = self._wizard()
        wizard.action_refresh_preview()
        self.assertEqual(len(self._logs("preview")), 1)

    def test_blocked_attempt_is_logged_once_and_without_pii(self):
        wizard = self._wizard(month="1", year=2026)  # sin liquidaciones
        # `assertRaises` de Odoo envuelve el bloque en un savepoint y lo
        # revierte, lo que borraría el registro de auditoría que queremos
        # comprobar. Por eso se captura la excepción a mano.
        raised = False
        try:
            wizard.generate("xlsx")
        except UserError:
            raised = True
        self.assertTrue(raised)
        logs = self._logs("xlsx")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs.result, "blocked")
        self.assertNotIn("Auditoría Sintética", logs.detail or "")

    def test_log_records_the_initiating_user(self):
        wizard = self._wizard()
        wizard.generate("xlsx")
        self.assertEqual(self._logs("xlsx").user_id, self.env.user)

    def test_excel_and_pdf_report_the_same_totals(self):
        """11. Paridad de totales entre Excel y PDF."""
        wizard = self._wizard()
        excel_dataset = wizard.generate("xlsx")
        report = self.env["report.step_hr_remuneration_book.consolidated_book"]
        pdf_dataset = report._get_report_values(self._wizard().ids)["dataset"]
        self.assertEqual(excel_dataset.totals, pdf_dataset.totals)
        self.assertEqual(excel_dataset.quantity, pdf_dataset.quantity)
        self.assertEqual(
            [group.name for group in excel_dataset.groups],
            [group.name for group in pdf_dataset.groups],
        )
