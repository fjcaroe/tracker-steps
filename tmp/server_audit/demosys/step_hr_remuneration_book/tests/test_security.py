"""Permisos corporativos, reporte parcial, aislamiento y rutas firmadas."""

import time

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from ..tools import dt_book
from .common import RemunerationBookCommon, RemunerationBookHttpCommon


@tagged("post_install", "-at_install")
class TestSecurity(RemunerationBookCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payroll_manager = cls.env["res.users"].create({
            "name": "Nómina Administradora Sintética",
            "login": "tst_payroll_manager",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, cls.company.ids)],
            "groups_id": [(4, cls.env.ref("hr_payroll.group_hr_payroll_manager").id)],
        })
        cls.payroll_user = cls.env["res.users"].create({
            "name": "Nómina Sintética",
            "login": "tst_payroll_user",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, cls.company.ids)],
            "groups_id": [(4, cls.env.ref("hr_payroll.group_hr_payroll_user").id)],
        })
        cls.plain_user = cls.env["res.users"].create({
            "name": "Sin Nómina Sintética",
            "login": "tst_plain_user",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, cls.company.ids)],
            "groups_id": [(4, cls.env.ref("base.group_user").id)],
        })
        employee = cls._create_employee("Ana Sintética", "12.345.678-5")
        cls._create_payslip(
            employee, cls._create_contract(employee, cls.department_admin),
            cls._coherent_values(wage=500000))

    # -- 1. permisos corporativos y reporte parcial --------------------------

    def test_user_without_payroll_group_is_rejected(self):
        wizard = self._wizard()
        with self.assertRaises(UserError):
            wizard.with_user(self.plain_user).build_dataset()

    def test_payroll_manager_can_generate_the_corporate_book(self):
        wizard = self._wizard().with_user(self.payroll_manager)
        dataset = wizard.build_dataset()
        self.assertEqual(dataset.quantity, 1)
        self.assertEqual(dataset.scope, dt_book.SCOPE_FULL)
        self.assertEqual(dataset.scope_label, "Alcance: empresa completa")

    def test_payroll_officer_cannot_produce_the_corporate_book(self):
        """El Encargado no tiene el grupo de exportación completa."""
        self.assertFalse(self.payroll_user.has_group(
            "step_hr_remuneration_book.group_remuneration_book_full"))
        wizard = self._wizard().with_user(self.payroll_user)
        with self.assertRaises(UserError):
            wizard.build_dataset()

    def test_partial_report_is_labelled_as_partial(self):
        wizard = self._wizard(mode="partial").with_user(self.payroll_manager)
        dataset = wizard.build_dataset()
        self.assertEqual(dataset.scope, dt_book.SCOPE_PARTIAL)
        self.assertEqual(dataset.scope_label, "Alcance parcial")

    def test_partial_report_never_offers_the_official_csv(self):
        wizard = self._wizard(mode="partial").with_user(self.payroll_manager)
        self.assertFalse(wizard.official_csv_available)
        with self.assertRaises(UserError):
            wizard.action_download_official_csv()

    def test_company_not_allowed_is_rejected(self):
        wizard = self.env["step.hr.remuneration.book.wizard"].create({
            "company_id": self.other_company.id, "month": "6", "year": 2026,
        })
        with self.assertRaises(UserError):
            wizard.with_user(self.payroll_manager).build_dataset()

    # -- 4. aislamiento multiempresa ----------------------------------------

    def test_report_of_one_company_never_mixes_another(self):
        foreign = self._create_employee("Ajeno Sintético", "88.888.888-8",
                                        company=self.other_company)
        self._create_payslip(
            foreign, self._create_contract(foreign),
            self._coherent_values(wage=777777), company=self.other_company)
        dataset = self._wizard().build_dataset()
        self.assertEqual(dataset.totals[dt_book.CODE_WAGE], 500000)
        self.assertNotIn("Ajeno Sintético",
                         [line.employee_name for line in dataset.lines])

    # -- auditoría -----------------------------------------------------------

    def test_audit_log_has_no_personal_data_and_names_the_real_user(self):
        wizard = self._wizard().with_user(self.payroll_manager)
        wizard.generate("xlsx")
        log = self.env["step.remuneration.book.log"].search(
            [("company_id", "=", self.company.id)], limit=1, order="id desc")
        self.assertTrue(log)
        self.assertEqual(log.output, "xlsx")
        self.assertEqual(log.line_count, 1)
        self.assertEqual(log.scope, dt_book.SCOPE_FULL)
        self.assertEqual(log.user_id, self.payroll_manager)
        text = " ".join(str(log[name] or "") for name in ("detail",))
        self.assertNotIn("Ana Sintética", text)
        self.assertNotIn("12345678", text)

    # -- 9. tolerancia cero y negativa ---------------------------------------

    def test_zero_tolerance_is_strict_and_not_replaced_by_the_default(self):
        employee = self._create_employee("Tolera Sintética", "10.000.003-2")
        contract = self._create_contract(employee, self.department_admin)
        values = self._coherent_values(wage=500000)
        # Una diferencia de 1 peso: dentro del valor por defecto, fuera de 0.
        values[dt_book.CODE_TOTAL_TAXABLE] += 1
        self._create_payslip(employee, contract, values)

        self.company.remuneration_book_tolerance = 1
        self.assertEqual(self._wizard()._tolerance(), 1)
        relaxed = self._wizard().build_dataset()
        self.assertFalse([issue for issue in relaxed.warnings
                          if issue.code == "recon_5210"])

        self.company.remuneration_book_tolerance = 0
        self.assertEqual(self._wizard()._tolerance(), 0)
        strict = self._wizard().build_dataset()
        self.assertTrue([issue for issue in strict.warnings
                         if issue.code == "recon_5210"])

    def test_negative_tolerance_is_rejected(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.company.remuneration_book_tolerance = -1
            self.company.flush_recordset()

    # -- 8. fechas mensuales manipuladas -------------------------------------

    def test_period_must_be_a_full_calendar_month(self):
        wizard = self._wizard()
        wizard._check_period_is_a_calendar_month()  # no debe lanzar
        self.assertEqual(str(wizard.date_from), "2026-06-01")
        self.assertEqual(str(wizard.date_to), "2026-06-30")


@tagged("post_install", "-at_install")
class TestSecurityRoutes(RemunerationBookHttpCommon):
    """Las rutas de descarga exigen token firmado, grupo, empresa y período."""

    URL = "/step/payroll/remuneration-book/xlsx"
    CSV_URL = "/step/payroll/remuneration-book/official-csv"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book_manager = cls.env["res.users"].create({
            "name": "Nómina HTTP Sintética",
            "login": "tst_http_payroll",
            "password": "tst_http_payroll_pwd",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, cls.company.ids)],
            "groups_id": [(4, cls.env.ref("hr_payroll.group_hr_payroll_manager").id)],
        })
        cls.officer = cls.env["res.users"].create({
            "name": "Encargado HTTP Sintético",
            "login": "tst_http_officer",
            "password": "tst_http_officer_pwd",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, cls.company.ids)],
            "groups_id": [(4, cls.env.ref("hr_payroll.group_hr_payroll_user").id)],
        })
        cls.plain_user = cls.env["res.users"].create({
            "name": "Sin Nómina HTTP Sintética",
            "login": "tst_http_plain",
            "password": "tst_http_plain_pwd",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, cls.company.ids)],
            "groups_id": [(4, cls.env.ref("base.group_user").id)],
        })
        employee = cls._create_employee("Ana HTTP Sintética", "12.345.678-5")
        cls._create_payslip(
            employee, cls._create_contract(employee, cls.department_admin),
            cls._coherent_values(wage=500000))

    def _signed_url(self, user=None, mode="full", output="xlsx",
                    route=None, company=None):
        user = user or self.book_manager
        wizard = self.env["step.hr.remuneration.book.wizard"].with_user(
            user
        ).create({
            "company_id": (company or self.company).id,
            "month": "6", "year": 2026, "mode": mode,
        })
        action = wizard._download_url(route or self.URL, output)
        return action["url"], wizard

    # -- 2. URL directa por usuario sin permisos -----------------------------

    def test_manager_downloads_the_workbook_with_a_signed_url(self):
        url, _wizard = self._signed_url()
        self.authenticate("tst_http_payroll", "tst_http_payroll_pwd")
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response.headers["Content-Type"])
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertTrue(response.content.startswith(b"PK"))

    def test_url_without_token_is_not_found(self):
        self.authenticate("tst_http_payroll", "tst_http_payroll_pwd")
        response = self.url_open(
            "%s?date_from=2026-06-01&date_to=2026-06-30&company_id=%s"
            % (self.URL, self.company.id))
        self.assertEqual(response.status_code, 404)

    def test_officer_cannot_guess_the_corporate_export(self):
        """Un Encargado no puede adivinar ni reutilizar la URL corporativa."""
        url, _wizard = self._signed_url()
        self.authenticate("tst_http_officer", "tst_http_officer_pwd")
        response = self.url_open(url)
        self.assertEqual(response.status_code, 404)

    def test_user_without_payroll_group_gets_not_found(self):
        url, _wizard = self._signed_url()
        self.authenticate("tst_http_plain", "tst_http_plain_pwd")
        response = self.url_open(url)
        self.assertEqual(response.status_code, 404)

    def test_tampered_token_is_rejected(self):
        url, _wizard = self._signed_url()
        self.authenticate("tst_http_payroll", "tst_http_payroll_pwd")
        tampered = url.replace("token=", "token=0")
        self.assertEqual(self.url_open(tampered).status_code, 404)

    def test_expired_token_is_rejected(self):
        wizard = self.env["step.hr.remuneration.book.wizard"].with_user(
            self.book_manager
        ).create({"company_id": self.company.id, "month": "6", "year": 2026})
        expired = int(time.time()) - 10
        token = wizard._download_token("xlsx", expired)
        url = ("%s?wizard_id=%s&output=xlsx&exp=%s&token=%s"
               "&date_from=2026-06-01&date_to=2026-06-30&company_id=%s"
               % (self.URL, wizard.id, expired, token, self.company.id))
        self.authenticate("tst_http_payroll", "tst_http_payroll_pwd")
        self.assertEqual(self.url_open(url).status_code, 404)

    # -- 8. fechas manipuladas -----------------------------------------------

    def test_manipulated_period_parameters_are_rejected(self):
        url, _wizard = self._signed_url()
        self.authenticate("tst_http_payroll", "tst_http_payroll_pwd")
        for replacement in (
            ("date_from=2026-06-01", "date_from=2026-06-02"),
            ("date_to=2026-06-30", "date_to=2026-07-31"),
            ("date_to=2026-06-30", "date_to=2026-06-15"),
            ("date_from=2026-06-01", "date_from=no-es-fecha"),
        ):
            response = self.url_open(url.replace(*replacement))
            self.assertEqual(response.status_code, 404)
            self.assertNotIn("Traceback", response.text)

    def test_missing_parameters_do_not_leak_a_traceback(self):
        self.authenticate("tst_http_payroll", "tst_http_payroll_pwd")
        for query in (self.URL, "%s?wizard_id=abc" % self.URL):
            response = self.url_open(query)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn("Traceback", response.text)

    def test_company_outside_the_session_is_rejected(self):
        url, _wizard = self._signed_url()
        self.authenticate("tst_http_payroll", "tst_http_payroll_pwd")
        response = self.url_open(url.replace(
            "company_id=%s" % self.company.id,
            "company_id=%s" % self.other_company.id))
        self.assertEqual(response.status_code, 404)

    def test_partial_mode_cannot_reach_the_official_csv_route(self):
        url, _wizard = self._signed_url(
            mode="partial", output="csv", route=self.CSV_URL)
        self.authenticate("tst_http_payroll", "tst_http_payroll_pwd")
        self.assertEqual(self.url_open(url).status_code, 404)
