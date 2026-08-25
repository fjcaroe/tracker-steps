"""12. El CSV oficial DT no se altera, y el adaptador se comporta igual.

La prueba se adapta a la base: si no hay una fuente oficial instalada, lo que
se comprueba es que el módulo lo diga con claridad y bloquee la salida en vez
de inventar un archivo. Si la hay, se comprueba que el archivo se entregue
íntegro, con las columnas y el delimitador del generador oficial.
"""

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from ..models import remuneration_book_adapter as adapters
from .common import RemunerationBookCommon, RemunerationBookHttpCommon


@tagged("post_install", "-at_install")
class TestOfficialCsv(RemunerationBookCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        employee = cls._create_employee("CSV Sintética", "12.345.678-5")
        cls._create_payslip(
            employee, cls._create_contract(employee, cls.department_admin),
            cls._coherent_values(wage=500000))

    def _source(self):
        return self.env["step.remuneration.book.extractor"].official_csv_source()

    def test_availability_matches_the_installed_source(self):
        module, label = self._source()
        wizard = self._wizard()
        self.assertEqual(wizard.official_csv_available, bool(module))
        if module:
            self.assertIn(label, wizard.official_csv_message)
        else:
            self.assertIn("No hay una fuente oficial DT instalada",
                          wizard.official_csv_message)

    def test_without_a_source_the_output_is_blocked_with_a_clear_message(self):
        module, _label = self._source()
        if module:
            self.skipTest("Hay una fuente oficial instalada en esta base.")
        wizard = self._wizard()
        with self.assertRaises(UserError):
            wizard.action_download_official_csv()
        with self.assertRaises(UserError):
            self.env["step.remuneration.book.extractor"].official_csv(wizard)


@tagged("post_install", "-at_install")
class TestOfficialCsvOverHttp(RemunerationBookHttpCommon):
    """El archivo oficial se pide por la ruta firmada, como en el producto.

    El generador de SimpleDigital vive dentro de un `http.Controller` y usa
    `request` internamente, así que sólo puede ejecutarse dentro de una
    petición HTTP. Por eso la comprobación de que el archivo llega íntegro se
    hace por la ruta y no llamando al modelo desde una prueba sin servidor.
    """

    CSV_URL = "/step/payroll/remuneration-book/official-csv"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book_manager = cls.env["res.users"].create({
            "name": "CSV HTTP Sintética",
            "login": "tst_csv_http",
            "password": "tst_csv_http_pwd",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, cls.company.ids)],
            "groups_id": [(4, cls.env.ref("hr_payroll.group_hr_payroll_manager").id)],
        })
        employee = cls._create_employee("CSV Sintética", "12.345.678-5")
        cls._create_payslip(
            employee, cls._create_contract(employee, cls.department_admin),
            cls._coherent_values(wage=500000))

    def test_official_csv_keeps_its_columns_and_delimiter(self):
        module, _label = self.env[
            "step.remuneration.book.extractor"].official_csv_source()
        if not module:
            self.skipTest("No hay fuente oficial DT instalada en esta base.")
        wizard = self.env["step.hr.remuneration.book.wizard"].with_user(
            self.book_manager
        ).create({"company_id": self.company.id, "month": "6", "year": 2026,
                  "mode": "full"})
        url = wizard._download_url(self.CSV_URL, "csv")["url"]
        self.authenticate("tst_csv_http", "tst_csv_http_pwd")
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("csv", response.headers["Content-Type"])
        rows = [row for row in response.content.decode("cp1252").splitlines()
                if row.strip()]
        self.assertTrue(rows)
        header = rows[0]
        self.assertIn(";", header)
        columns = len(header.split(";"))
        # El libro consolidado tiene 24 columnas; el archivo oficial es otro
        # producto y debe conservar TODAS las suyas.
        self.assertGreater(columns, 24)
        for row in rows[1:]:
            self.assertEqual(len(row.split(";")), columns)


@tagged("post_install", "-at_install")
class TestAdapterRuntime(RemunerationBookCommon):
    """Comportamiento de los adaptadores cuando el proveedor sí está."""

    def test_adapters_return_an_empty_mapping_without_records(self):
        employee = self._create_employee("Adaptador Sintético", "12.345.678-5")
        payslip = self._create_payslip(
            employee, self._create_contract(employee, self.department_admin),
            self._coherent_values())
        for key, adapter in adapters.ADAPTERS.items():
            if not adapter.is_installed(self.env):
                continue
            values = adapter.values(
                self.env, payslip, adapter.allowed_params()[0])
            self.assertIsInstance(values, dict, key)
            for payslip_id in values:
                self.assertEqual(payslip_id, payslip.id, key)

    def test_adapter_scoping_uses_the_report_companies(self):
        employee = self._create_employee("Ámbito Sintético", "11.111.111-1")
        payslip = self._create_payslip(
            employee, self._create_contract(employee, self.department_admin),
            self._coherent_values())
        for key, adapter in adapters.ADAPTERS.items():
            if not adapter.is_installed(self.env):
                continue
            scoped = adapter._scoped(self.env, payslip)
            self.assertEqual(
                scoped.env.context.get("allowed_company_ids"),
                self.company.ids, key)
